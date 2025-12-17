"""
Preliminary Report Service
==========================
AI-powered preliminary report generation for the "Early Analysis" feature.
Follows the document_analysis_service.py pattern for lightweight LLM calls.
"""

import hashlib
import html
import json
import logging
from typing import AsyncGenerator, List, Optional
from uuid import UUID

from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Case, Document, ReportVersion
from app.schemas.enums import ExtractionStatus

logger = logging.getLogger(__name__)


class PreliminaryReportError(Exception):
    """Raised when preliminary report generation fails."""

    pass


class PreliminaryBlockedError(Exception):
    """Raised when documents are still being processed."""

    pass


def compute_document_hash(documents: List[Document]) -> str:
    """
    Compute a hash of document IDs to detect changes.
    Same pattern as document_analysis_service.
    """
    if not documents:
        return hashlib.sha256(b"").hexdigest()
    sorted_ids = sorted(str(doc.id) for doc in documents)
    combined = "|".join(sorted_ids)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def get_latest_preliminary_report(
    case_id: UUID, db: AsyncSession
) -> Optional[ReportVersion]:
    """
    Retrieve the most recent preliminary report for a case.

    Preliminary reports are stored as ReportVersion with is_final=False
    and source='preliminary'.

    Args:
        case_id: The case UUID
        db: Async database session

    Returns:
        ReportVersion or None if no preliminary report exists
    """
    stmt = (
        select(ReportVersion)
        .where(
            ReportVersion.case_id == case_id,
            ReportVersion.source == "preliminary",  # Only preliminary reports
        )
        .order_by(ReportVersion.created_at.desc())
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


async def run_preliminary_report(
    case_id: UUID, org_id: UUID, db: AsyncSession, force: bool = False
) -> ReportVersion:
    """
    Generate an AI preliminary report for a case.

    This function:
    1. Checks if documents are still processing (blocks if so)
    2. Collects all extracted document content
    3. Sends to Gemini for preliminary report generation
    4. Stores the result as a ReportVersion

    Args:
        case_id: The case UUID
        org_id: The organization UUID (for tenant isolation)
        db: Async database session
        force: If True, regenerate even if existing report exists

    Returns:
        ReportVersion object containing the preliminary report

    Raises:
        PreliminaryBlockedError: If documents are still processing
        PreliminaryReportError: If LLM call fails
    """
    # 1. Check for pending documents
    has_pending, pending_count = await check_has_pending_documents(case_id, db)
    if has_pending:
        raise PreliminaryBlockedError(
            f"Cannot generate report: {pending_count} documents are still being processed"
        )

    # 2. Fetch current documents for hash comparison
    docs_stmt = (
        select(Document)
        .where(Document.case_id == case_id)
        .where(Document.ai_status == ExtractionStatus.SUCCESS)
    )
    docs_result = await db.execute(docs_stmt)
    documents = list(docs_result.scalars().all())
    current_hash = compute_document_hash(documents)

    # 3. Check for existing report (unless force=True)
    if not force:
        existing = await get_latest_preliminary_report(case_id, db)
        if existing:
            # Check if documents have changed since last report
            # We store the hash in template_used field as a workaround
            # (avoids schema migration)
            cached_hash = existing.template_used or ""
            if cached_hash == current_hash:
                logger.info(f"Returning existing preliminary report for case {case_id}")
                return existing
            else:
                logger.info(f"Documents changed, regenerating preliminary report for case {case_id}")

    if not documents:
        raise PreliminaryBlockedError("No documents available for report generation")

    # 3b. Fetch case with relationships for context
    case_result = await db.execute(
        select(Case)
        .options(selectinload(Case.client), selectinload(Case.assicurato_rel))
        .where(Case.id == case_id)
    )
    case = case_result.scalar_one_or_none()

    # 4. Build prompt content from extracted data
    document_contents = []
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
                if isinstance(entry, dict) and entry.get("type") == "text":
                    content = entry.get("content", "")
                    if content:
                        document_contents.append(
                            {
                                "filename": doc.filename,
                                "content": content[:15000],  # Limit per-doc content
                            }
                        )

    # 5. Load prompt template
    from app.core.prompt_config import prompt_manager

    try:
        system_prompt = prompt_manager.get_prompt_content("preliminary_report")
    except (ValueError, FileNotFoundError) as e:
        logger.warning(
            f"Preliminary prompt not in PromptManager, loading directly: {e}"
        )
        import os

        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "core", "preliminary_report_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

    # 6. Build the evidence section
    evidence_parts = []
    for doc_data in document_contents:
        safe_filename = html.escape(doc_data["filename"])
        evidence_parts.append(
            f'<document filename="{safe_filename}">\n{doc_data["content"]}\n</document>'
        )
    evidence_section = "\n".join(evidence_parts)

    # 6b. Build confirmed data context
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

    full_prompt = (
        f"{system_prompt}\n\n{context_block}<case_documents>\n{evidence_section}\n</case_documents>"
    )

    # 7. Call Gemini API (Markdown output, not JSON)
    logger.info(
        f"Generating preliminary report for case {case_id} with {len(documents)} documents"
    )

    try:
        # Use Vertex AI mode for consistency with other services
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GEMINI_API_LOCATION,
        )

        response = await client.aio.models.generate_content(
            model=settings.GEMINI_PRELIMINARY_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,  # Slightly higher for more natural writing
                max_output_tokens=8000,
                # No response_mime_type - we want Markdown text
            ),
        )

        if not response or not response.text:
            raise PreliminaryReportError("Empty response from model")

        report_content = response.text

        # 8. Lock the case row BEFORE version calculation to prevent TOCTOU race
        # This ensures the read(max) + increment + insert is atomic
        await db.execute(
            select(Case).where(Case.id == case_id).with_for_update()
        )

        # 9. Get next version number (safe now, we hold the lock)
        from sqlalchemy import func

        max_version_result = await db.execute(
            select(func.coalesce(func.max(ReportVersion.version_number), 0)).where(
                ReportVersion.case_id == case_id
            )
        )
        next_version = max_version_result.scalar() + 1

        # 10. Create and persist the ReportVersion
        new_version = ReportVersion(
            case_id=case_id,
            organization_id=org_id,
            ai_raw_output=report_content,
            is_final=False,
            source="preliminary",  # Mark as preliminary report
            version_number=next_version,
            template_used=current_hash,  # Store hash for staleness detection
        )

        db.add(new_version)
        await db.commit()
        await db.refresh(new_version)

        logger.info(
            f"Preliminary report generated for case {case_id}, length: {len(report_content)}"
        )

        return new_version

    except PreliminaryReportError:
        raise
    except Exception as e:
        logger.error(
            f"Preliminary report failed for case {case_id}: {e}", exc_info=True
        )
        raise PreliminaryReportError(f"Report generation failed: {str(e)}") from None


async def _build_preliminary_prompt(
    case_id: UUID, db: AsyncSession
) -> tuple[str, List[Document]]:
    """
    Build the prompt for preliminary report generation.

    Returns:
        Tuple of (full_prompt, documents)

    Raises:
        PreliminaryBlockedError: If documents are pending or none available
    """
    # Check for pending documents
    has_pending, pending_count = await check_has_pending_documents(case_id, db)
    if has_pending:
        raise PreliminaryBlockedError(
            f"Cannot generate report: {pending_count} documents are still being processed"
        )

    # Fetch current documents
    docs_stmt = (
        select(Document)
        .where(Document.case_id == case_id)
        .where(Document.ai_status == ExtractionStatus.SUCCESS)
    )
    docs_result = await db.execute(docs_stmt)
    documents = list(docs_result.scalars().all())

    if not documents:
        raise PreliminaryBlockedError("No documents available for report generation")

    # Fetch case with relationships for context
    case_result = await db.execute(
        select(Case)
        .options(selectinload(Case.client), selectinload(Case.assicurato_rel))
        .where(Case.id == case_id)
    )
    case = case_result.scalar_one_or_none()

    # Build prompt content from extracted data
    document_contents = []
    for doc in documents:
        if doc.ai_extracted_data:
            extracted = doc.ai_extracted_data
            if isinstance(extracted, dict):
                entries = extracted.get("entries", [])
            elif isinstance(extracted, list):
                entries = extracted
            else:
                entries = []

            for entry in entries:
                if isinstance(entry, dict) and entry.get("type") == "text":
                    if content := entry.get("content", ""):
                        document_contents.append(
                            {
                                "filename": doc.filename,
                                "content": content[:15000],
                            }
                        )

    # Load prompt template
    from app.core.prompt_config import prompt_manager

    try:
        system_prompt = prompt_manager.get_prompt_content("preliminary_report")
    except (ValueError, FileNotFoundError) as e:
        logger.warning(
            f"Preliminary prompt not in PromptManager, loading directly: {e}"
        )
        import os

        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "core", "preliminary_report_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

    # Build evidence section
    evidence_parts = []
    for doc_data in document_contents:
        safe_filename = html.escape(doc_data["filename"])
        evidence_parts.append(
            f'<document filename="{safe_filename}">\n{doc_data["content"]}\n</document>'
        )
    evidence_section = "\n".join(evidence_parts)

    # Build confirmed data context
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

    full_prompt = (
        f"{system_prompt}\n\n{context_block}<case_documents>\n{evidence_section}\n</case_documents>"
    )

    return full_prompt, documents


async def stream_preliminary_report(
    case_id: UUID, org_id: UUID, db: AsyncSession
) -> AsyncGenerator[str, None]:
    """
    Stream AI preliminary report with visible reasoning/thoughts.

    Yields NDJSON events in format:
        {"type": "thought", "text": "..."} - AI reasoning (hidden from final output)
        {"type": "content", "text": "..."} - Actual report content
        {"type": "done", "text": ""} - Stream complete
        {"type": "error", "text": "..."} - Error occurred

    Args:
        case_id: The case UUID
        org_id: The organization UUID
        db: Async database session

    Yields:
        NDJSON string lines
    """
    try:
        # Build prompt (validates documents, etc.)
        full_prompt, documents = await _build_preliminary_prompt(case_id, db)
        current_hash = compute_document_hash(documents)

        logger.info(
            f"Streaming preliminary report for case {case_id} with {len(documents)} documents"
        )

        # Use Vertex AI mode for consistency with other services
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GEMINI_API_LOCATION,
        )

        # Configure with ThinkingConfig to enable thought visibility
        # Note: include_thoughts=True works with gemini-2.5-pro/flash models
        config = types.GenerateContentConfig(
            temperature=0.5,
            max_output_tokens=8000,
            thinking_config=types.ThinkingConfig(
                include_thoughts=True
            )
        )

        # Accumulate full content for storage
        full_content = ""

        # Open streaming response
        response = await client.aio.models.generate_content_stream(
            model=settings.GEMINI_PRELIMINARY_MODEL,
            contents=full_prompt,
            config=config
        )

        async for chunk in response:
            if chunk.candidates and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    # Check if this part is a thought or final answer
                    # The SDK sets part.thought=True for reasoning tokens
                    is_thought = getattr(part, "thought", False)
                    text = part.text or ""

                    if text:
                        event = {
                            "type": "thought" if is_thought else "content",
                            "text": text
                        }
                        yield json.dumps(event) + "\n"

                        # Only accumulate non-thought content for storage
                        if not is_thought:
                            full_content += text

        # Store the generated report
        if full_content:
            # Lock case row for version calculation
            await db.execute(
                select(Case).where(Case.id == case_id).with_for_update()
            )

            from sqlalchemy import func
            max_version_result = await db.execute(
                select(func.coalesce(func.max(ReportVersion.version_number), 0)).where(
                    ReportVersion.case_id == case_id
                )
            )
            next_version = max_version_result.scalar() + 1

            new_version = ReportVersion(
                case_id=case_id,
                organization_id=org_id,
                ai_raw_output=full_content,
                is_final=False,
                source="preliminary",
                version_number=next_version,
                template_used=current_hash,
            )

            db.add(new_version)
            await db.commit()

            logger.info(
                f"Streamed preliminary report saved for case {case_id}, length: {len(full_content)}"
            )

        # Signal completion
        yield json.dumps({"type": "done", "text": ""}) + "\n"

    except PreliminaryBlockedError as e:
        logger.warning(f"Streaming blocked for case {case_id}: {e}")
        yield json.dumps({"type": "error", "text": str(e)}) + "\n"
    except Exception as e:
        logger.error(f"Streaming failed for case {case_id}: {e}", exc_info=True)
        yield json.dumps({"type": "error", "text": f"Report generation failed: {str(e)}"}) + "\n"

