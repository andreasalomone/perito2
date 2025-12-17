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

    summary: str = Field(description="Brief Italian summary of the case documents")
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

    # 3. Fetch all documents with their extracted data
    docs_stmt = (
        select(Document)
        .where(Document.case_id == case_id)
        .where(Document.ai_status == ExtractionStatus.SUCCESS)
    )
    docs_result = await db.execute(docs_stmt)
    documents = docs_result.scalars().all()

    if not documents:
        raise AnalysisBlockedError("No documents available for analysis")

    # 3b. Fetch case with relationships for context
    case_result = await db.execute(
        select(Case)
        .options(selectinload(Case.client), selectinload(Case.assicurato_rel))
        .where(Case.id == case_id)
    )
    case = case_result.scalar_one_or_none()

    # 4. Build prompt content from extracted data
    document_contents: List[dict[str, str]] = []
    vision_parts: List[dict[str, Any]] = (
        []
    )  # NEW: List to hold Part objects for vision files

    for doc in documents:
        if doc.ai_extracted_data:
            # Handle both formats: list directly or dict with "entries" key
            extracted = doc.ai_extracted_data
            if isinstance(extracted, dict):
                entries = extracted.get("entries", [])
            elif isinstance(extracted, list):
                entries = extracted
            else:
                entries = []

            for entry in entries:
                if isinstance(entry, dict):
                    entry_type = entry.get("type")
                    if entry_type == "text":
                        # Text content - add to text section
                        content = entry.get("content", "")
                        if content:
                            document_contents.append(
                                {
                                    "filename": doc.filename,
                                    "content": content[:10000],  # Limit per-doc content
                                }
                            )
                    elif entry_type == "vision":
                        # Vision file (PDF/image) - create Part for Gemini
                        gcs_path = entry.get("gcs_path")
                        mime_type = entry.get("mime_type")
                        if gcs_path and mime_type:
                            try:
                                vision_part = types.Part.from_uri(
                                    file_uri=gcs_path, mime_type=mime_type
                                )
                                vision_parts.append(
                                    {
                                        "part": vision_part,
                                        "filename": doc.filename,
                                    }
                                )
                                logger.debug(
                                    f"Added vision file to analysis: {doc.filename}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to create Part for {doc.filename}: {e}"
                                )

    # 5. Load prompt template
    from app.core.prompt_config import prompt_manager

    try:
        system_prompt = prompt_manager.get_prompt_content("document_analysis")
    except (ValueError, FileNotFoundError) as e:
        logger.warning(f"Analysis prompt not in PromptManager, loading directly: {e}")
        # Fallback: load directly from file
        import os

        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "core", "document_analysis_prompt.txt"
        )

        def read_prompt_file():
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()

        system_prompt = await asyncio.to_thread(read_prompt_file)

    # 6. Build the evidence section (text documents)
    evidence_parts = []
    for doc_data in document_contents:
        safe_filename = html.escape(str(doc_data["filename"]))
        evidence_parts.append(
            f'<document filename="{safe_filename}">\n{doc_data["content"]}\n</document>'
        )
    evidence_section = "\n".join(evidence_parts)

    # 6b. NEW: Add vision file names to context so LLM knows they exist
    vision_filenames = [v["filename"] for v in vision_parts]
    if vision_filenames:
        vision_list = "\n".join(f"- {html.escape(fn)}" for fn in vision_filenames)
        vision_section = f"\n\n<attached_vision_files>\nThe following files are attached as images for visual analysis:\n{vision_list}\n</attached_vision_files>"
    else:
        vision_section = ""

    # 6c. Build confirmed data context
    context_block = ""
    if case:
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
        context_block = (
            f"<confirmed_data>\n"
            f"Il nostro cliente per questo sinistro è: {client_info}.\n"
            f"Il Ns. Rif (nostro riferimento interno) è: {safe_ref}.\n"
            f"L'assicurato di questo caso è: {safe_assicurato}.\n"
            f"</confirmed_data>\n\n"
        )

    full_prompt = f"{system_prompt}\n\n{context_block}<case_documents>\n{evidence_section}\n</case_documents>{vision_section}"

    # 7. Build multimodal content array
    # Start with the text prompt
    content_parts: List[types.Part | str] = [full_prompt]

    # Add vision parts (real file references)
    for vision_item in vision_parts:
        content_parts.append(cast(types.Part, vision_item["part"]))

    # 8. Call Gemini API with JSON output (now multimodal)
    logger.info(
        f"Running document analysis for case {case_id} with {len(documents)} documents "
        f"({len(document_contents)} text, {len(vision_parts)} vision)"
    )

    try:
        # Use Vertex AI mode for direct GCS access via Part.from_uri()
        # API key mode does NOT support gs:// URIs
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GEMINI_API_LOCATION,
        )

        response = await client.aio.models.generate_content(
            model=settings.GEMINI_DOC_ANALYSIS_MODEL,
            contents=content_parts,  # type: ignore
            config=types.GenerateContentConfig(
                temperature=0.2,  # Lower for more consistent structured output
                max_output_tokens=8000,  # Increased to prevent truncation
                response_mime_type="application/json",
                response_schema=DocumentAnalysisSchema,  # Force valid JSON structure
            ),
        )

        if not response or not response.text:
            raise AnalysisGenerationError("Empty response from analysis model")

        # 8. Parse JSON response
        import json

        try:
            analysis_data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse analysis JSON: {e}\nRaw: {response.text[:500]}"
            )
            raise AnalysisGenerationError(f"Invalid JSON from model: {e}") from None

        # 9. Extract fields with defaults
        summary = analysis_data.get("summary", "Analisi non disponibile")
        received_docs = analysis_data.get("received_docs", [])
        missing_docs = analysis_data.get("missing_docs", [])

        # Ensure they're lists
        if not isinstance(received_docs, list):
            received_docs = [str(received_docs)] if received_docs else []
        if not isinstance(missing_docs, list):
            missing_docs = [str(missing_docs)] if missing_docs else []

        # 10. Fetch all docs again for hash (including non-SUCCESS)
        all_docs_stmt = select(Document).where(Document.case_id == case_id)
        all_docs_result = await db.execute(all_docs_stmt)
        all_documents = all_docs_result.scalars().all()

        # 11. Create and persist the analysis
        document_hash = compute_document_hash(list(all_documents))

        new_analysis = DocumentAnalysis(
            case_id=case_id,
            organization_id=org_id,
            summary=summary,
            received_docs=received_docs,
            missing_docs=missing_docs,
            document_hash=document_hash,
            is_stale=False,
        )

        db.add(new_analysis)
        await db.commit()
        await db.refresh(new_analysis)

        logger.info(
            f"Analysis complete for case {case_id}: "
            f"{len(received_docs)} received, {len(missing_docs)} missing"
        )

        return new_analysis

    except AnalysisGenerationError:
        raise
    except Exception as e:
        logger.error(f"Document analysis failed for case {case_id}: {e}", exc_info=True)
        raise AnalysisGenerationError(f"Analysis failed: {str(e)}") from None
