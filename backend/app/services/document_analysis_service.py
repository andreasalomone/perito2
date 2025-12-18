"""
Document Analysis Service
=========================
AI-powered document analysis for the "Early Analysis" feature.
Follows the summary_service.py pattern for lightweight LLM calls.
"""

import asyncio
import hashlib
import html
import logging
from typing import Any, List, Optional, Sequence, cast
from uuid import UUID

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Case, Document, DocumentAnalysis
from app.schemas.enums import ExtractionStatus

logger = logging.getLogger(__name__)


# Pydantic schema for LLM structured output
class DocumentAnalysisSchema(BaseModel):
    """Schema for document analysis LLM response."""

    summary: str = Field(
        description="Ultra-brief Italian case summary in 3-4 sentences (max 150 words). NO bullet points. Identify: claim type, goods, client, apparent cause, critical points."
    )
    received_docs: List[str] = Field(
        description="List of document types received (Italian)"
    )
    missing_docs: List[str] = Field(
        description="List of potentially missing documents (Italian)"
    )


# Custom exceptions for better error handling
class AnalysisBlockedError(Exception):
    """Raised when documents are still being processed."""

    pass


class AnalysisGenerationError(Exception):
    """Raised when LLM analysis fails."""

    pass


def compute_document_hash(documents: Sequence[Document]) -> str:
    """
    Compute a SHA-256 hash of sorted document IDs.

    This hash is used to detect staleness: if documents are added/removed,
    the hash changes, making the previous analysis stale.

    Args:
        documents: List of Document objects

    Returns:
        64-character hex string (SHA-256 hash)
    """
    if not documents:
        return hashlib.sha256(b"").hexdigest()

    # Sort document IDs for consistent hashing
    sorted_ids = sorted(str(doc.id) for doc in documents)
    combined = "|".join(sorted_ids)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def get_latest_analysis(
    case_id: UUID, db: AsyncSession
) -> Optional[DocumentAnalysis]:
    """
    Retrieve the most recent document analysis for a case.

    Args:
        case_id: The case UUID
        db: Async database session

    Returns:
        DocumentAnalysis or None if no analysis exists
    """
    stmt = (
        select(DocumentAnalysis)
        .where(DocumentAnalysis.case_id == case_id)
        .order_by(DocumentAnalysis.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def check_has_pending_documents(
    case_id: UUID, db: AsyncSession
) -> tuple[bool, int]:
    """
    Check if any documents are still being processed.

    Args:
        case_id: The case UUID
        db: Async database session

    Returns:
        Tuple of (has_pending, pending_count)
    """
    stmt = select(Document).where(
        Document.case_id == case_id,
        Document.ai_status.in_([ExtractionStatus.PENDING, ExtractionStatus.PROCESSING]),
    )
    result = await db.execute(stmt)
    pending_docs = result.scalars().all()
    return len(pending_docs) > 0, len(pending_docs)


async def check_analysis_staleness(
    case_id: UUID, db: AsyncSession
) -> tuple[bool, Optional[DocumentAnalysis]]:
    """
    Check if the most recent analysis is stale.

    An analysis is stale if:
    1. Documents have been added since the analysis
    2. Documents have been deleted since the analysis

    Args:
        case_id: The case UUID
        db: Async database session

    Returns:
        Tuple of (is_stale, latest_analysis)
    """
    # Get current documents
    docs_stmt = select(Document).where(Document.case_id == case_id)
    docs_result = await db.execute(docs_stmt)
    current_docs = docs_result.scalars().all()

    # Get latest analysis
    analysis = await get_latest_analysis(case_id, db)

    if not analysis:
        return True, None  # No analysis = needs one

    # Compare hashes
    current_hash = compute_document_hash(current_docs)
    is_stale = analysis.document_hash != current_hash

    # Update staleness flag if changed
    if is_stale and not analysis.is_stale:
        analysis.is_stale = True
        await db.commit()

    return is_stale, analysis


def _extract_entries_from_document(extracted: Any) -> List[dict[str, Any]]:
    """Extract entries list from ai_extracted_data in either format."""
    if isinstance(extracted, dict):
        return cast(List[dict[str, Any]], extracted.get("entries", []))
    if isinstance(extracted, list):
        return extracted
    return []


def _process_text_entry(
    entry: dict[str, Any], filename: str, document_contents: List[dict[str, str]]
) -> None:
    """Process a text entry and append to document_contents if valid."""
    content = entry.get("content", "")
    if content:
        document_contents.append(
            {
                "filename": filename,
                "content": content[:10000],  # Limit per-doc content
            }
        )


def _process_vision_entry(
    entry: dict[str, Any], filename: str, vision_parts: List[dict[str, Any]]
) -> None:
    """Process a vision entry and append to vision_parts if valid."""
    gcs_path = entry.get("gcs_path")
    mime_type = entry.get("mime_type")
    if not (gcs_path and mime_type):
        return

    try:
        vision_part = types.Part.from_uri(file_uri=gcs_path, mime_type=mime_type)
        vision_parts.append({"part": vision_part, "filename": filename})
        logger.debug(f"Added vision file to analysis: {filename}")
    except Exception as e:
        logger.warning(f"Failed to create Part for {filename}: {e}")


def _extract_document_contents(
    documents: Sequence[Document],
) -> tuple[List[dict[str, str]], List[dict[str, Any]]]:
    """
    Extract text and vision content from documents.

    Returns:
        Tuple of (document_contents, vision_parts)
    """
    document_contents: List[dict[str, str]] = []
    vision_parts: List[dict[str, Any]] = []

    for doc in documents:
        if not doc.ai_extracted_data:
            continue

        entries = _extract_entries_from_document(doc.ai_extracted_data)
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            entry_type = entry.get("type")
            if entry_type == "text":
                _process_text_entry(entry, doc.filename, document_contents)
            elif entry_type == "vision":
                _process_vision_entry(entry, doc.filename, vision_parts)

    return document_contents, vision_parts


async def _load_system_prompt() -> str:
    """Load the document analysis system prompt with fallback."""
    from app.core.prompt_config import prompt_manager

    try:
        return prompt_manager.get_prompt_content("document_analysis")
    except (ValueError, FileNotFoundError) as e:
        logger.warning(f"Analysis prompt not in PromptManager, loading directly: {e}")

    # Fallback: load directly from file
    import os

    prompt_path = os.path.join(
        os.path.dirname(__file__), "..", "core", "document_analysis_prompt.txt"
    )

    def read_prompt_file() -> str:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    return await asyncio.to_thread(read_prompt_file)


def _build_evidence_section(document_contents: List[dict[str, str]]) -> str:
    """Build XML evidence section from document contents."""
    evidence_parts = []
    for doc_data in document_contents:
        safe_filename = html.escape(str(doc_data["filename"]))
        evidence_parts.append(
            f'<document filename="{safe_filename}">\n{doc_data["content"]}\n</document>'
        )
    return "\n".join(evidence_parts)


def _build_vision_section(vision_parts: List[dict[str, Any]]) -> str:
    """Build vision files context section."""
    vision_filenames = [v["filename"] for v in vision_parts]
    if not vision_filenames:
        return ""

    vision_list = "\n".join(f"- {html.escape(fn)}" for fn in vision_filenames)
    return (
        f"\n\n<attached_vision_files>\n"
        f"The following files are attached as images for visual analysis:\n"
        f"{vision_list}\n</attached_vision_files>"
    )


def _build_context_block(case: Optional[Case]) -> str:
    """Build confirmed data context block from case."""
    if not case:
        return ""

    from app.services.report_generation_service import _build_case_context

    case_context = _build_case_context(case)
    safe_ref = html.escape(case_context.get("ref_code", "N.D."))
    safe_client = html.escape(case_context.get("client_name", "N.D."))
    safe_assicurato = html.escape(case_context.get("assicurato_name", "N.D."))

    location_parts = [
        case_context.get("client_address_street"),
        case_context.get("client_zip_code"),
        case_context.get("client_city"),
        case_context.get("client_province"),
        case_context.get("client_country"),
    ]
    location_str = ", ".join(html.escape(p) for p in location_parts if p)
    client_info = f"{safe_client}, {location_str}" if location_str else safe_client

    return (
        f"<confirmed_data>\n"
        f"Il nostro cliente per questo sinistro è: {client_info}.\n"
        f"Il Ns. Rif (nostro riferimento interno) è: {safe_ref}.\n"
        f"L'assicurato di questo caso è: {safe_assicurato}.\n"
        f"</confirmed_data>\n\n"
    )


def _check_response_truncation(response: Any, case_id: UUID) -> None:
    """Check if LLM response was truncated and raise if so."""
    if not (response.candidates and response.candidates[0].finish_reason):
        return

    finish_reason = response.candidates[0].finish_reason
    reason_name = (
        finish_reason.name if hasattr(finish_reason, "name") else str(finish_reason)
    )

    if reason_name not in ("STOP", "1"):
        logger.warning(
            f"Response truncated for case {case_id}: finish_reason={reason_name}"
        )
        raise AnalysisGenerationError(
            f"Response truncated (finish_reason={reason_name}). Please retry."
        )


def _parse_analysis_response(response_text: str) -> dict[str, Any]:
    """Parse and validate the JSON response from the LLM."""
    import json

    try:
        analysis_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse analysis JSON: {e}\nRaw: {response_text[:500]}")
        raise AnalysisGenerationError(f"Invalid JSON from model: {e}") from None

    # Extract fields with defaults and ensure they're lists
    summary = analysis_data.get("summary", "Analisi non disponibile")
    received_docs = analysis_data.get("received_docs", [])
    missing_docs = analysis_data.get("missing_docs", [])

    if not isinstance(received_docs, list):
        received_docs = [str(received_docs)] if received_docs else []
    if not isinstance(missing_docs, list):
        missing_docs = [str(missing_docs)] if missing_docs else []

    return {
        "summary": summary,
        "received_docs": received_docs,
        "missing_docs": missing_docs,
    }


async def _call_gemini_analysis(
    content_parts: List[types.Part | str], case_id: UUID
) -> dict[str, Any]:
    """Call Gemini API for document analysis and return parsed result."""
    client = genai.Client(
        vertexai=True,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GEMINI_API_LOCATION,
    )

    response = await client.aio.models.generate_content(
        model=settings.GEMINI_DOC_ANALYSIS_MODEL,
        contents=content_parts,  # type: ignore
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16000,
            response_mime_type="application/json",
            response_schema=DocumentAnalysisSchema,
        ),
    )

    if not response or not response.text:
        raise AnalysisGenerationError("Empty response from analysis model")

    _check_response_truncation(response, case_id)
    return _parse_analysis_response(response.text)


async def run_document_analysis(
    case_id: UUID, org_id: UUID, db: AsyncSession, force: bool = False
) -> DocumentAnalysis:
    """
    Run AI document analysis for a case.

    This function:
    1. Checks if documents are still processing (blocks if so)
    2. Collects all extracted document content
    3. Sends to Gemini for analysis
    4. Stores the result with current document hash

    Args:
        case_id: The case UUID
        org_id: The organization UUID (for tenant isolation)
        db: Async database session
        force: If True, regenerate even if existing analysis is not stale

    Returns:
        DocumentAnalysis object

    Raises:
        AnalysisBlockedError: If documents are still processing
        AnalysisGenerationError: If LLM call fails
    """
    # 1. Check for pending documents
    has_pending, pending_count = await check_has_pending_documents(case_id, db)
    if has_pending:
        raise AnalysisBlockedError(
            f"Cannot analyze: {pending_count} documents are still being processed"
        )

    # 2. Check staleness (unless force=True)
    if not force:
        is_stale, existing_analysis = await check_analysis_staleness(case_id, db)
        if existing_analysis and not is_stale:
            logger.info(f"Returning cached analysis for case {case_id} (not stale)")
            return existing_analysis

    # 3. Fetch documents with SUCCESS status
    docs_stmt = (
        select(Document)
        .where(Document.case_id == case_id)
        .where(Document.ai_status == ExtractionStatus.SUCCESS)
    )
    docs_result = await db.execute(docs_stmt)
    documents = docs_result.scalars().all()

    if not documents:
        raise AnalysisBlockedError("No documents available for analysis")

    # 4. Fetch case with relationships for context
    case_result = await db.execute(
        select(Case)
        .options(selectinload(Case.client), selectinload(Case.assicurato_rel))
        .where(Case.id == case_id)
    )
    case = case_result.scalar_one_or_none()

    # 5. Extract content from documents
    document_contents, vision_parts = _extract_document_contents(documents)

    # 6. Build prompt components
    system_prompt = await _load_system_prompt()
    evidence_section = _build_evidence_section(document_contents)
    vision_section = _build_vision_section(vision_parts)
    context_block = _build_context_block(case)

    full_prompt = (
        f"{system_prompt}\n\n{context_block}"
        f"<case_documents>\n{evidence_section}\n</case_documents>"
        f"{vision_section}"
    )

    # 7. Build multimodal content array
    content_parts: List[types.Part | str] = [full_prompt]
    for vision_item in vision_parts:
        content_parts.append(cast(types.Part, vision_item["part"]))

    logger.info(
        f"Running document analysis for case {case_id} with {len(documents)} documents "
        f"({len(document_contents)} text, {len(vision_parts)} vision)"
    )

    # 8. Call Gemini and get parsed result
    try:
        analysis_data = await _call_gemini_analysis(content_parts, case_id)
    except AnalysisGenerationError:
        raise
    except Exception as e:
        logger.error(f"Document analysis failed for case {case_id}: {e}", exc_info=True)
        raise AnalysisGenerationError(f"Analysis failed: {str(e)}") from None

    # 9. Fetch all docs for hash (including non-SUCCESS)
    all_docs_stmt = select(Document).where(Document.case_id == case_id)
    all_docs_result = await db.execute(all_docs_stmt)
    all_documents = all_docs_result.scalars().all()

    # 10. Create and persist the analysis
    document_hash = compute_document_hash(list(all_documents))
    new_analysis = DocumentAnalysis(
        case_id=case_id,
        organization_id=org_id,
        summary=analysis_data["summary"],
        received_docs=analysis_data["received_docs"],
        missing_docs=analysis_data["missing_docs"],
        document_hash=document_hash,
        is_stale=False,
    )

    db.add(new_analysis)
    await db.commit()
    await db.refresh(new_analysis)

    logger.info(
        f"Analysis complete for case {case_id}: "
        f"{len(analysis_data['received_docs'])} received, "
        f"{len(analysis_data['missing_docs'])} missing"
    )

    return new_analysis
