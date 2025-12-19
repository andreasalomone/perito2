import asyncio
import copy
import json
import logging
from typing import AsyncGenerator, Optional

from google.cloud import tasks_v2
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import Case, Document, ReportVersion
from app.schemas.enums import CaseStatus, ExtractionStatus
from app.services import case_service, docx_generator
from app.services.gcs_service import get_storage_client
from app.services.llm_handler import ProcessedFile, gemini_generator

logger = logging.getLogger(__name__)


# NOTE: Phase 3 optimization removed the download step - we now use Part.from_uri() directly


async def run_generation_task(
    case_id: str,
    organization_id: str,
    language: str = "italian",
    extra_instructions: Optional[str] = None,
):
    """
    Wrapper for background execution that manages its own ASYNC DB session.
    Uses AsyncSessionLocal for proper async database operations.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Set RLS context for the background session (async style)
            await db.execute(
                text("SELECT set_config('app.current_org_id', :org_id, false)"),
                {"org_id": organization_id},
            )

            await generate_report_logic(
                case_id,
                organization_id,
                db,
                language=language,
                extra_instructions=extra_instructions,
            )
        except Exception as e:
            logger.error(f"Async generation task failed: {e}")
            await db.rollback()
            raise


async def run_process_case_logic_standalone(case_id: str, organization_id: str):
    """
    Wrapper for background execution that manages its own ASYNC DB session.
    Used by Cloud Tasks to process cases safely without sharing sessions across threads.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Set RLS context for the background session (async style)
            await db.execute(
                text("SELECT set_config('app.current_org_id', :org_id, false)"),
                {"org_id": organization_id},
            )

            await process_case_logic(case_id, organization_id, db)
        except Exception as e:
            logger.error(f"Async case processing task failed: {e}")
            await db.rollback()
            raise


async def process_case_logic(case_id: str, organization_id: str, db: AsyncSession):
    """
    Phase 1: Dispatch Tasks
    Iterates all documents and dispatches a 'process-document' Cloud Task for each.
    """
    # 1. Setup - Get Case with locking to prevent race conditions
    result = await db.execute(select(Case).filter(Case.id == case_id).with_for_update())
    case = result.scalars().first()
    if not case:
        logger.error(f"Case {case_id} not found in DB")
        return

    # DUPLICATE PREVENTION: Check if already processing (now atomic with lock)
    if case.status == CaseStatus.PROCESSING:
        logger.warning(
            f"Case {case_id} already processing, skipping duplicate dispatch"
        )
        return

    # Update status to processing
    case.status = CaseStatus.PROCESSING
    await db.commit()

    # 2. Fetch Documents
    result = await db.execute(select(Document).filter(Document.case_id == case_id))
    documents = result.scalars().all()

    # FIX BUG-4: Handle empty document list
    if not documents:
        logger.error(f"No documents found for case {case_id}. Marking case as ERROR.")
        # Re-acquire lock to update status
        result = await db.execute(
            select(Case).filter(Case.id == case_id).with_for_update()
        )
        case = result.scalars().first()
        if case:
            case.status = CaseStatus.ERROR
            await db.commit()
        return

    # 3. Dispatch Tasks
    for doc in documents:
        if doc.ai_status == ExtractionStatus.SUCCESS:
            continue

        # For local dev, process inline instead of dispatching tasks
        if settings.RUN_LOCALLY:
            logger.info(f"Local mode: Processing document {doc.id} inline")
            await case_service.process_document_extraction(doc.id, organization_id, db)
        else:
            # Dispatch Cloud Task
            # PERF FIX: Wrap sync function in asyncio.to_thread() to prevent blocking
            await asyncio.to_thread(
                case_service.trigger_extraction_task, doc.id, organization_id
            )

    # NOTE: We do NOT auto-trigger generation here.
    # Users must explicitly click "Genera con IA" when ready.

    # Reset status back to OPEN after dispatching all tasks
    # The PROCESSING status was set to prevent duplicate dispatch attempts (race condition guard).
    # Now that dispatch is complete, the case should be OPEN while documents are processed.
    result = await db.execute(select(Case).filter(Case.id == case_id).with_for_update())
    case = result.scalars().first()
    if case and case.status == CaseStatus.PROCESSING:
        case.status = CaseStatus.OPEN
        await db.commit()
        logger.info(
            f"Case {case_id} status reset to OPEN after dispatching document tasks"
        )


async def trigger_generation_task(
    case_id: str,
    organization_id: str,
    language: str = "italian",
    extra_instructions: Optional[str] = None,
):
    """
    Enqueues the 'generate-report' task.
    """
    if settings.RUN_LOCALLY:
        logger.info(f"Running generation locally for case {case_id}")
        # Run in background (fire and forget) or await if we want to block
        # Since this is usually called from a task or API, we can just run it.
        # But we need a fresh DB session if we run it directly.
        await run_generation_task(
            case_id,
            organization_id,
            language=language,
            extra_instructions=extra_instructions,
        )
        return

    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/api/v1/tasks/generate-report",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.CLOUD_RUN_AUDIENCE_URL,  # Use Cloud Run URL, not custom domain
                },
                "body": json.dumps(
                    {
                        "case_id": case_id,
                        "organization_id": organization_id,
                        "language": language,
                        "extra_instructions": extra_instructions,
                    }
                ).encode(),
            }
        }

        logger.info(
            f"🚀 Enqueuing generation task for case {case_id} with language: {language}"
        )
        # PERF FIX: Wrap sync gRPC call in asyncio.to_thread() to prevent event loop blocking
        await asyncio.to_thread(
            client.create_task, request={"parent": parent, "task": task}
        )

    except Exception as e:
        logger.error(f"Failed to enqueue generation task for case {case_id}: {e}")
        # Re-raise to propagate error
        # This allows document workers to retry completion check
        raise


# --- Helper functions to reduce cognitive complexity of generate_report_logic ---


async def _check_existing_report(case_id: str, case: Case, db: AsyncSession) -> bool:
    """Check if report already exists in DB. Returns True if we should abort generation."""
    result = await db.execute(
        select(ReportVersion).filter(
            ReportVersion.case_id == case_id, ReportVersion.version_number == 1
        )
    )
    if result.scalars().first():
        logger.info(
            f"Report for case {case_id} already exists. Aborting duplicate generation."
        )
        if case.status != CaseStatus.OPEN:
            case.status = CaseStatus.OPEN
            await db.commit()
        return True
    return False


async def _recover_orphaned_report(
    case_id: str, organization_id: str, case: Case, db: AsyncSession
) -> bool:
    """
    Check if report exists in GCS but not in DB (partial failure recovery).
    Returns True if recovery was successful and we should abort generation.
    """
    bucket_name = settings.STORAGE_BUCKET_NAME
    expected_blob_name = f"reports/{organization_id}/{case_id}/v1_AI_Draft.docx"

    try:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(expected_blob_name)
        gcs_path_exists = await asyncio.to_thread(blob.exists)

        if not gcs_path_exists:
            return False

        logger.warning(
            f"Found orphaned report in GCS for case {case_id}. "
            f"Recovering by creating DB record without regenerating."
        )
        v1 = ReportVersion(
            case_id=case_id,
            organization_id=organization_id,
            version_number=1,
            docx_storage_path=f"gs://{bucket_name}/{expected_blob_name}",
            ai_raw_output="[Recovered from GCS - original AI output not available]",
            is_final=False,
            source="final",  # Mark as final report source
        )
        db.add(v1)
        case.status = CaseStatus.OPEN
        await db.commit()
        logger.info(f"✅ Recovered orphaned report for case {case_id}")
        return True
    except Exception as e:
        logger.warning(
            f"Could not check GCS for existing report: {e}. Proceeding with generation."
        )
        return False


async def _validate_documents_ready(
    case_id: str, case: Case, db: AsyncSession
) -> list | None:
    """
    Validate that documents are ready for generation.
    Returns list of documents if ready, None if generation should abort.
    """
    result = await db.execute(select(Document).filter(Document.case_id == case_id))
    all_docs = result.scalars().all()

    if pending_docs := [
        d
        for d in all_docs
        if d.ai_status
        not in [
            ExtractionStatus.SUCCESS,
            ExtractionStatus.ERROR,
            ExtractionStatus.SKIPPED,
        ]
    ]:
        logger.info(
            f"Case {case_id} has pending documents: {[d.id for d in pending_docs]}. Resetting status and aborting generation."
        )
        # FIX: Reset status to OPEN to prevent "Stuck Generating" state
        case.status = CaseStatus.OPEN
        await db.commit()
        return None

    # Check if we have at least one processed document
    has_completed_docs = any(d.ai_status == ExtractionStatus.SUCCESS for d in all_docs)
    if not has_completed_docs:
        logger.error(
            f"Cannot generate report for case {case_id}: No successfully processed documents found."
        )
        case.status = CaseStatus.ERROR
        await db.commit()
        return None

    processed_count = sum(d.ai_status == ExtractionStatus.SUCCESS for d in all_docs)
    error_count = sum(d.ai_status == ExtractionStatus.ERROR for d in all_docs)
    logger.info(
        f"Starting generation for case {case_id} with {processed_count} processed and {error_count} failed documents."
    )

    return list(all_docs)


def _process_vision_item(item: dict, doc_gcs_path: str | None) -> None:
    """Process a single vision item, setting up GCS URI."""
    target_gcs_path = item.get("item_gcs_path") or doc_gcs_path

    if not target_gcs_path:
        logger.warning(f"Item {item.get('filename', 'unknown')} has no GCS source.")
        item["type"] = "error"
        item["error"] = "Missing GCS source path"
        return

    # Ensure fully qualified gs:// URI for Vertex AI
    if not target_gcs_path.startswith("gs://"):
        target_gcs_path = f"gs://{settings.STORAGE_BUCKET_NAME}/{target_gcs_path}"

    item["gcs_uri"] = target_gcs_path
    item["local_path"] = None
    logger.debug(
        f"Using GCS direct access for {item.get('filename', 'asset')}: {target_gcs_path}"
    )


def _deep_copy_extracted_data(doc: Document) -> dict | list:
    """Deep copy extracted data to prevent mutating SQLAlchemy object."""
    original_data_id = id(doc.ai_extracted_data)
    data = copy.deepcopy(doc.ai_extracted_data)
    assert original_data_id != id(data), f"Deep copy failed for document {doc.id}."
    return data


def _process_document_for_llm(doc: Document) -> tuple[list[dict], dict | None]:
    """
    Process a single document for LLM input.
    Returns (processed_items, failed_doc_info or None).
    """
    if doc.ai_status == ExtractionStatus.SUCCESS and doc.ai_extracted_data:
        data = _deep_copy_extracted_data(doc)

        if isinstance(data, dict):
            data = [data]

        for item in data:
            if item.get("type") == "vision":
                _process_vision_item(item, doc.gcs_path)

        return data, None

    if doc.ai_status == ExtractionStatus.ERROR:
        logger.warning(
            f"Document {doc.id} ({doc.filename}) failed processing - skipping"
        )
        return [], {
            "id": str(doc.id),
            "filename": doc.filename,
            "reason": "Processing failed",
        }

    # Document still pending or other status
    logger.warning(
        f"Document {doc.id} ({doc.filename}) is not processed (Status: {doc.ai_status}). Skipping."
    )
    return [], {
        "id": str(doc.id),
        "filename": doc.filename,
        "reason": f"Status: {doc.ai_status}",
    }


def _deduplicate_by_content_hash(items: list[dict]) -> list[dict]:
    """
    Remove duplicates and filter useless item types.

    - Skips: unsupported, error, warning types
    - Items WITH hash: deduplicate by hash
    - Items WITHOUT hash (legacy): always include
    """
    SKIP_TYPES = {"unsupported", "error", "warning"}

    seen_hashes: set[str] = set()
    result = []
    duplicates_removed = 0
    filtered_out = 0

    for item in items:
        # Skip useless items
        if item.get("type") in SKIP_TYPES:
            filtered_out += 1
            continue

        content_hash = item.get("content_hash")

        if content_hash:
            if content_hash in seen_hashes:
                duplicates_removed += 1
                continue  # Skip duplicate
            seen_hashes.add(content_hash)

        # Include item (either unique hash or no hash)
        result.append(item)

    if duplicates_removed > 0 or filtered_out > 0:
        logger.info(
            f"🔁 Filtering: {duplicates_removed} duplicates + {filtered_out} unsupported "
            f"→ {len(result)} items remain"
        )

    return result


async def _collect_documents_for_generation(
    case_id: str, db: AsyncSession
) -> tuple[list[dict], list[dict], int]:
    """
    Collect and process all documents for LLM generation.
    Returns (processed_data_for_llm, failed_docs, total_doc_count).
    """
    result = await db.execute(select(Document).filter(Document.case_id == case_id))
    documents = result.scalars().all()

    processed_data_for_llm = []
    failed_docs = []

    # Tracking counters for detailed logging
    vision_count = 0
    text_count = 0
    success_docs = 0
    error_docs = 0
    pending_docs = 0

    for doc in documents:
        items, failed_info = _process_document_for_llm(doc)

        # Count document types for logging
        if doc.ai_status == ExtractionStatus.SUCCESS:
            success_docs += 1
            for item in items:
                item_type = item.get("type", "unknown")
                if item_type == "vision":
                    vision_count += 1
                elif item_type == "text":
                    text_count += 1
        elif doc.ai_status == ExtractionStatus.ERROR:
            error_docs += 1
        else:
            pending_docs += 1

        processed_data_for_llm.extend(items)
        if failed_info:
            failed_docs.append(failed_info)

    # Detailed logging for document flow tracing
    logger.info(
        f"📊 Document Flow for case {case_id}: "
        f"{len(documents)} total docs → "
        f"{success_docs} SUCCESS, {error_docs} ERROR, {pending_docs} PENDING/OTHER"
    )
    logger.info(
        f"📊 LLM Input Summary for case {case_id}: "
        f"{len(processed_data_for_llm)} items before dedup → "
        f"{vision_count} vision, {text_count} text"
    )
    if failed_docs:
        for fd in failed_docs:
            logger.warning(f"  ⚠️ Skipped: {fd['filename']} - Reason: {fd['reason']}")

    # Deduplicate items with identical content hashes
    processed_data_for_llm = _deduplicate_by_content_hash(processed_data_for_llm)

    return processed_data_for_llm, failed_docs, len(documents)


def _build_case_context(case: Case) -> dict[str, str]:
    """Build case context dict for LLM prompt. Uses actual DB field names."""
    ctx = {
        "ref_code": case.reference_code or "N.D.",
        "client_name": "N.D.",
        "client_address_street": "",
        "client_zip_code": "",
        "client_city": "",
        "client_province": "",
        "client_country": "",
        "assicurato_name": "N.D.",
    }

    # Client enriched data - ensure strings
    if case.client:
        ctx["client_name"] = str(case.client.name) if case.client.name else "N.D."
        ctx["client_address_street"] = (
            str(case.client.address_street)
            if isinstance(case.client.address_street, str)
            and case.client.address_street
            else ""
        )
        ctx["client_zip_code"] = (
            str(case.client.zip_code)
            if isinstance(case.client.zip_code, str) and case.client.zip_code
            else ""
        )
        ctx["client_city"] = (
            str(case.client.city)
            if isinstance(case.client.city, str) and case.client.city
            else ""
        )
        ctx["client_province"] = (
            str(case.client.province)
            if isinstance(case.client.province, str) and case.client.province
            else ""
        )
        ctx["client_country"] = (
            str(case.client.country)
            if isinstance(case.client.country, str) and case.client.country
            else ""
        )

    # Assicurato: prefer relationship (user-selected), fallback to string (AI-extracted)
    if (
        case.assicurato_rel
        and hasattr(case.assicurato_rel, "name")
        and isinstance(case.assicurato_rel.name, str)
    ):
        ctx["assicurato_name"] = case.assicurato_rel.name
    elif case.assicurato and isinstance(case.assicurato, str):
        ctx["assicurato_name"] = case.assicurato

    return ctx


async def _generate_and_upload_report(
    processed_data_for_llm: list[dict],
    case_id: str,
    organization_id: str,
    language: str,
    extra_instructions: Optional[str] = None,
    case_context: Optional[dict[str, str]] = None,
) -> tuple[str, str]:
    """
    Generate report with Gemini and upload DOCX to GCS.
    Returns (report_text, final_docx_path).
    """
    logger.info("Generating text with Gemini...")
    processed_files_models = [ProcessedFile(**item) for item in processed_data_for_llm]

    report_result = await gemini_generator.generate(
        processed_files=processed_files_models,
        language=language,
        extra_instructions=extra_instructions,
        case_context=case_context,
    )
    report_text = report_result.content

    logger.info("Generating DOCX...")
    docx_stream = await asyncio.to_thread(
        docx_generator.create_styled_docx, report_text
    )

    bucket_name = settings.STORAGE_BUCKET_NAME
    blob_name = f"reports/{organization_id}/{case_id}/v1_AI_Draft.docx"

    def upload_blob():
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(
            docx_stream,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        return f"gs://{bucket_name}/{blob_name}"

    final_docx_path = await asyncio.to_thread(upload_blob)
    return report_text, final_docx_path


async def _save_report_version(
    case_id: str,
    organization_id: str,
    report_text: str,
    final_docx_path: str,
    db: AsyncSession,
) -> None:
    """Save the generated report as Version 1 and optionally generate summary."""
    result = await db.execute(select(Case).filter(Case.id == case_id).with_for_update())
    case = result.scalars().first()

    if not case:
        raise ValueError(
            f"Case {case_id} disappeared during generation. "
            f"Likely deleted manually. Marking as permanent failure."
        )

    if case.status == CaseStatus.ERROR:
        logger.warning(
            "Case marked as error by another process during generation. Overwriting with success."
        )

    result = await db.execute(
        select(ReportVersion).filter(
            ReportVersion.case_id == case_id, ReportVersion.version_number == 1
        )
    )
    if v1 := result.scalars().first():
        v1.docx_storage_path = final_docx_path
        v1.ai_raw_output = report_text
        v1.source = "final"  # Ensure source is set for updates

    else:
        v1 = ReportVersion(
            case_id=case_id,
            organization_id=organization_id,
            version_number=1,
            docx_storage_path=final_docx_path,
            ai_raw_output=report_text,
            is_final=False,
            source="final",  # Mark as final report source
        )
        db.add(v1)
    case.status = CaseStatus.OPEN
    try:
        await db.commit()
        logger.info("✅ Case processing completed successfully. Version 1 created.")
    except IntegrityError:
        await db.rollback()
        logger.error(
            f"IntegrityError saving Version 1 for case {case_id}. Likely race condition."
        )
        raise

    # Summary generation moved to case_service.finalize_case (when status becomes CLOSED)


async def _handle_generation_error(
    case_id: str, error: Exception, db: AsyncSession
) -> None:
    """Handle errors during report generation by updating case status."""
    logger.error(f"❌ Error during generation: {error}", exc_info=True)
    try:
        await db.rollback()
        result = await db.execute(
            select(Case).filter(Case.id == case_id).with_for_update()
        )
        if case := result.scalars().first():
            case.status = CaseStatus.ERROR
            await db.commit()
    except Exception as db_e:
        logger.error(f"Failed to update case status to error: {db_e}")

    logger.critical(
        f"🛑 Stopping Cloud Task retry loop for case {case_id} due to error: {error}"
    )


async def generate_report_logic(
    case_id: str,
    organization_id: str,
    db: AsyncSession,
    language: str = "italian",
    extra_instructions: Optional[str] = None,
):
    """
    Phase 2: Generation
    Called when all documents are processed.
    1. Aggregates data.
    2. Generates AI Report.
    3. Creates Version 1.

    Args:
        case_id: The case UUID
        organization_id: The organization UUID
        db: The async database session
        language: The target output language for the report (italian, english, spanish)
        extra_instructions: Optional additional instructions from expert
    """
    # 1. Fetch case with lock (eager load client + assicurato for case_context)
    result = await db.execute(
        select(Case)
        .options(selectinload(Case.client), selectinload(Case.assicurato_rel))
        .filter(Case.id == case_id)
        .with_for_update()
    )
    case = result.scalars().first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    # Clear old summary to avoid stale data (Summary only regenerates on Finalization)
    case.ai_summary = None
    await db.commit()

    # 2. Idempotency checks
    if await _check_existing_report(case_id, case, db):
        return

    if await _recover_orphaned_report(case_id, organization_id, case, db):
        return

    # 3. Set status and validate documents
    case.status = CaseStatus.GENERATING
    await db.commit()

    all_docs = await _validate_documents_ready(case_id, case, db)
    if all_docs is None:
        return

    # Release lock before long-running AI operations
    await db.commit()

    try:
        # 4. Collect documents for generation
        processed_data_for_llm, failed_docs, total_docs = (
            await _collect_documents_for_generation(case_id, db)
        )

        if not processed_data_for_llm:
            logger.error("No processed data available for generation.")
            raise ValueError("No processed data found")

        # Log summary
        logger.info(
            f"Generating report from {len(processed_data_for_llm)}/{total_docs} documents "
            f"({len(failed_docs)} failed/skipped)"
        )
        if failed_docs:
            logger.warning(f"Failed documents: {[d['filename'] for d in failed_docs]}")

        # Build case context BEFORE releasing lock (while case is still loaded)
        case_context = _build_case_context(case)

        # 5. Generate and upload report
        report_text, final_docx_path = await _generate_and_upload_report(
            processed_data_for_llm,
            case_id,
            organization_id,
            language,
            extra_instructions=extra_instructions,
            case_context=case_context,
        )

        # 6. Save version and generate summary
        await _save_report_version(
            case_id, organization_id, report_text, final_docx_path, db
        )

    except Exception as e:
        await _handle_generation_error(case_id, e, db)


async def stream_final_report(
    case_id: str,
    organization_id: str,
    db: AsyncSession,
    language: str = "italian",
    extra_instructions: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Orchestrates streaming final report generation.
    Yields NDJSON strings.
    """
    # 1. Fetch case for context
    result = await db.execute(
        select(Case)
        .options(selectinload(Case.client), selectinload(Case.assicurato_rel))
        .filter(Case.id == case_id)
    )
    case = result.scalars().first()
    if not case:
        yield json.dumps({"type": "error", "text": "Case not found"}) + "\n"
        return

    # Clear old summary to avoid stale data in preview fallbacks
    case.ai_summary = None
    await db.commit()
    await db.refresh(case)

    # 2. Validation
    # NOTE: We skip idempotency check (force generation) for interactive requests usually,
    # or we could check existing report. For now, interactive means "do it now".

    # Check docs
    all_docs = await _validate_documents_ready(case_id, case, db)
    if all_docs is None:
        yield json.dumps({"type": "error", "text": "Documents are not ready"}) + "\n"
        return

    # Check if already finalized
    existing_final = await db.execute(
        select(ReportVersion).filter(
            ReportVersion.case_id == case_id, ReportVersion.is_final.is_(True)
        )
    )
    if existing_final.scalars().first():
        yield json.dumps(
            {
                "type": "error",
                "text": "The case is already finalized (ReportFinalizedError).",
            }
        ) + "\n"
        return

    # Check if active draft exists (Google Docs)
    active_draft_res = await db.execute(
        select(ReportVersion).filter(
            ReportVersion.case_id == case_id,
            ReportVersion.is_draft_active.is_(True),
            ReportVersion.is_final.is_(False),
        )
    )
    if active_draft_res.scalars().first():
        yield json.dumps(
            {
                "type": "error",
                "text": "A live draft is currently active in Google Docs. Please sync or close usage before regenerating.",
            }
        ) + "\n"
        return

    try:
        # 3. Collect Data
        processed_data, failed_docs, _ = await _collect_documents_for_generation(
            case_id, db
        )
        if not processed_data:
            yield json.dumps(
                {"type": "error", "text": "No processed data found"}
            ) + "\n"
            return

        # 4. Build Context & Models
        case_context = _build_case_context(case)
        processed_files_models = [ProcessedFile(**item) for item in processed_data]

        # 5. Stream from LLM
        # Use the NEW parallel method
        acc_text = ""
        async for event in gemini_generator.generate_stream(
            processed_files=processed_files_models,
            language=language,
            extra_instructions=extra_instructions,
            case_context=case_context,
        ):
            # Pass through thoughts and content
            yield json.dumps(event) + "\n"
            if event["type"] == "content":
                acc_text += event["text"]

        # 6. Post-processing (DOCX + DB)
        if acc_text:
            # Generate DOCX
            docx_stream = await asyncio.to_thread(
                docx_generator.create_styled_docx, acc_text
            )
            bucket_name = settings.STORAGE_BUCKET_NAME
            blob_name = f"reports/{organization_id}/{case_id}/v1_AI_Draft.docx"

            def upload_blob():
                storage_client = get_storage_client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.upload_from_file(
                    docx_stream,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                return f"gs://{bucket_name}/{blob_name}"

            final_docx_path = await asyncio.to_thread(upload_blob)

            # Save Version (re-acquire lock to be safe/atomic)
            await _save_report_version(
                case_id, organization_id, acc_text, final_docx_path, db
            )

        yield json.dumps({"type": "done", "text": ""}) + "\n"

    except Exception as e:
        logger.error(f"Streaming failed: {e}", exc_info=True)
        yield json.dumps({"type": "error", "text": str(e)}) + "\n"


async def generate_docx_variant(
    version_id: str, template_type: str, db: Session
) -> str:
    """
    Generates a DOCX variant (BN or Salomone) on the fly from an existing ReportVersion.
    Returns the signed URL for the generated file.
    """
    # 1. Fetch Version
    version = db.query(ReportVersion).filter(ReportVersion.id == version_id).first()
    if not version:
        raise ValueError("Report version not found")

    if not version.ai_raw_output:
        raise ValueError("No AI content found for this version")

    # 2. Select Generator
    if template_type == "salomone":
        from app.services import docx_generator_salomone as generator

        suffix = "_Salomone.docx"
    elif template_type == "bn":
        from app.services import docx_generator as generator

        suffix = "_BN.docx"
    elif template_type == "default":
        from app.services import docx_generator_default as generator

        suffix = "_Default.docx"
    else:
        raise ValueError("Invalid template type")

    # 3. Generate DOCX
    logger.info(f"Generating DOCX variant {template_type} for version {version_id}...")
    docx_stream = await asyncio.to_thread(
        generator.create_styled_docx, version.ai_raw_output
    )

    # 4. Upload to GCS
    bucket_name = settings.STORAGE_BUCKET_NAME
    # Use a specific path for variants to avoid overwriting the main one if desired,
    # or overwrite if we want to switch 'default'.
    # Let's use a variant path: reports/{org}/{case}/variants/{ver_id}_{type}.docx
    blob_name = f"reports/{version.organization_id}/{version.case_id}/variants/{version.id}{suffix}"

    def upload_blob():
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        # Reset stream pointer just in case
        if hasattr(docx_stream, "seek"):
            docx_stream.seek(0)
        blob.upload_from_file(
            docx_stream,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        return blob

    await asyncio.to_thread(upload_blob)

    # 5. Generate Signed URL (Read)
    # Use gcs_service helper which handles IAM SignBlob for Cloud Run
    from app.services.gcs_service import generate_download_signed_url

    gcs_path = f"gs://{bucket_name}/{blob_name}"
    url = generate_download_signed_url(gcs_path)

    return url
