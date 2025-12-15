import asyncio
import json
import logging
import os
import shutil
import tempfile
from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from google.cloud import tasks_v2
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.models import Case, Client, Document, MLTrainingPair, ReportVersion, User
from app.schemas.enums import CaseStatus, ExtractionStatus
from app.services import document_processor
from app.services.gcs_service import download_file_to_temp, get_storage_client

# Limit concurrent extractions to prevent filling up memory/disk
# Use asyncio.Semaphore for async contexts.
extraction_semaphore = asyncio.Semaphore(9)  # Increased for 30-50 doc batch workloads

logger = logging.getLogger(__name__)


from sqlalchemy.exc import IntegrityError

from app.db.database import AsyncSessionLocal


def get_or_create_client(db: Session, name: str, organization_id: UUID) -> Client:
    if client := (
        db.query(Client)
        .filter(Client.name == name, Client.organization_id == organization_id)
        .first()
    ):
        return client

    # 2. Try to create (Handle Race Condition with SAVEPOINT)
    # Verified by backend/tests/test_client_creation_race.py
    # Use begin_nested() to create a SAVEPOINT
    try:
        with db.begin_nested():
            client = Client(name=name, organization_id=organization_id)
            db.add(client)
            db.flush()  # Flush within the savepoint
        # Savepoint successful - client.id is now available
        return client

    except IntegrityError:
        # Rollback happens automatically to the savepoint, not the whole transaction
        # Another process created the client, so fetch it
        return (
            db.query(Client)
            .filter(Client.name == name, Client.organization_id == organization_id)
            .one()
        )


# --- THE CRITICAL WORKFLOWS ---


def validate_storage_path(
    raw_path: str, org_id: UUID, case_id: UUID, allowed_prefixes: List[str]
) -> str:
    """
    Sanitizes and validates that a GCS path belongs to the specific case context.
    Prevents Path Traversal and IDOR (Insecure Direct Object Reference).
    """
    # 1. Traversal Check
    if ".." in raw_path or "~" in raw_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path characters detected.",
        )

    # 2. Normalize: Remove 'gs://bucket/' prefix if present
    clean_path = raw_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")

    # 3. Context Validation
    # Ensure the path starts with one of the allowed prefixes for this specific Org/Case
    # Expected format: <prefix>/{org_id}/{case_id}/
    valid_starts = [
        f"{prefix.strip('/')}/{org_id}/{case_id}/" for prefix in allowed_prefixes
    ]

    if not any(clean_path.startswith(v) for v in valid_starts):
        logger.warning(
            f"Security Alert: IDOR attempt. "
            f"Path '{clean_path}' does not match context {org_id}/{case_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security violation: File path does not belong to this case.",
        )

    return clean_path


def create_case_with_client(
    db: Session, case_data: schemas.CaseCreate, user_uid: str, user_org_id: UUID
) -> Case:
    """
    Encapsulates case creation logic including:
    - User validation
    - Client lookup/creation (CRM)
    - Transaction management
    """
    try:
        logger.info(f"Creating case for user {user_uid}")

        # 1. Fetch User (Strict Check)
        user = db.query(User).filter(User.id == user_uid).first()
        if not user:
            raise HTTPException(status_code=403, detail="User account not found.")

        # 2. CRM Logic (Get or Create Client) + ICE Enrichment Trigger
        client_id = None
        client = None
        is_new_client = False

        if case_data.client_name:
            # Check if client already exists BEFORE get_or_create (for enrichment trigger)
            existing_client = (
                db.query(Client)
                .filter(
                    Client.name == case_data.client_name,
                    Client.organization_id == user_org_id,
                )
                .first()
            )

            client = get_or_create_client(db, case_data.client_name, user_org_id)
            client_id = client.id

            # If we didn't find existing, client is new → trigger enrichment
            is_new_client = existing_client is None

        # 3. Create Case
        new_case = Case(
            reference_code=case_data.reference_code,
            organization_id=user_org_id,
            client_id=client_id,
            creator_id=user_uid,
            status=CaseStatus.OPEN,
        )

        db.add(new_case)
        db.commit()

        # RE-APPLY RLS CONTEXT
        # db.commit() releases the connection to the pool.
        # db.refresh() starts a new transaction, potentially on a cleaner/different connection.
        # We must ensure app.current_org_id is set to allow visibility of the new row.
        try:
            db.execute(
                text("SELECT set_config('app.current_org_id', :oid, false)"),
                {"oid": str(user_org_id)},
            )
            # Re-apply user_uid too just in case (though org_id is the key for row visibility)
            db.execute(
                text("SELECT set_config('app.current_user_uid', :uid, false)"),
                {"uid": user_uid},
            )
        except Exception as e:
            logger.warning(f"Failed to re-apply RLS context before refresh: {e}")

        db.refresh(new_case)

        # 4. Reload relationships for Pydantic
        # Manually assign to avoid lazy load issues after commit if session is closed/expired
        new_case.client = client
        new_case.creator = user
        new_case.documents = []
        new_case.report_versions = []

        # 5. ICE: Trigger background enrichment for NEW clients only
        if is_new_client and client and case_data.client_name:
            trigger_client_enrichment_task(str(client.id), case_data.client_name)

        return new_case

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating case: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create case: {str(e)}"
        ) from e


def create_ai_version(
    db: Session, case_id: UUID, org_id: UUID, ai_text: str, docx_path: str
):
    """
    Called by the Worker after Gemini finishes.
    Creates Version 1 (or next version).
    """
    # 0. LOCK the Case to prevent version race conditions
    # This ensures only one transaction can add a version at a time for this case.
    db.query(Case).filter(Case.id == case_id).with_for_update().first()

    # 1. Determine version number (Robust: Use MAX + 1, not COUNT)
    from sqlalchemy import func

    max_ver = (
        db.query(func.max(ReportVersion.version_number))
        .filter(ReportVersion.case_id == case_id)
        .scalar()
    )
    next_version = (max_ver or 0) + 1

    # 2. Save Version
    version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=next_version,
        docx_storage_path=docx_path,
        ai_raw_output=ai_text,
        is_final=False,
    )
    db.add(version)

    try:
        db.commit()
        return version
    except IntegrityError:
        db.rollback()
        # Retry logic or fail gracefully
        # Since we locked the case, this should rarely happen unless manual DB intervention
        logger.error(
            f"IntegrityError creating version {next_version} for case {case_id}"
        )
        raise


def finalize_case(db: Session, case_id: UUID, org_id: UUID, final_docx_path: str):
    """
    Called when User uploads the final "signed" PDF/DOCX.
    1. Save new version.
    2. Mark as Final.
    3. Create ML Training Pair.
    4. Set case status to CLOSED.
    """
    # 1. Create Final Version
    # LOCK the Case to prevent version race conditions
    # FIX: Capture the case object to update its status later
    case = db.query(Case).filter(Case.id == case_id).with_for_update().first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    from sqlalchemy import func

    max_ver = (
        db.query(func.max(ReportVersion.version_number))
        .filter(ReportVersion.case_id == case_id)
        .scalar()
    )
    next_version = (max_ver or 0) + 1

    final_version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=next_version,
        docx_storage_path=final_docx_path,
        is_final=True,
    )
    db.add(final_version)
    try:
        db.flush()  # Get ID
    except IntegrityError:
        db.rollback()
        logger.error(
            f"IntegrityError creating final version {next_version} for case {case_id}"
        )
        raise

    if ai_version := (
        db.query(ReportVersion)
        .filter(
            ReportVersion.case_id == case_id,
            ReportVersion.is_final.is_(False),
            ReportVersion.ai_raw_output.isnot(None),  # Ensure it has AI content
        )
        .order_by(ReportVersion.version_number.desc())
        .first()
    ):
        # 3. THE GOLD MINE: Create Training Pair
        pair = MLTrainingPair(
            case_id=case_id,
            ai_version_id=ai_version.id,
            final_version_id=final_version.id,
        )
        db.add(pair)
        logger.info(
            f"Created ML training pair: AI version {ai_version.version_number} -> Final version {next_version}"
        )
    else:
        logger.warning(
            f"No AI draft version found for case {case_id}. ML training pair not created."
        )

    # 4. CRITICAL FIX: Set case status to CLOSED
    # This enables proper workflow step detection in the frontend
    case.status = CaseStatus.CLOSED
    logger.info(f"Case {case_id} finalized and set to CLOSED status")

    db.commit()

    # 5. Trigger async extraction of case details
    # MUST be AFTER commit to ensure case is in CLOSED state
    try:
        trigger_case_details_extraction_task(
            case_id=str(case_id),
            organization_id=str(org_id),
            final_docx_path=final_docx_path,
            overwrite_existing=False,  # Preserve existing manual entries
        )
    except Exception as e:
        # Don't fail finalization if extraction trigger fails
        logger.error(f"Failed to trigger case details extraction: {e}")

    return final_version


def trigger_extraction_task(doc_id: UUID, org_id: str):
    """
    Enqueues a task to Cloud Tasks to process the document.
    """
    if settings.RUN_LOCALLY:
        # Local dev: run extraction in background thread
        # CRITICAL: We must create a NEW async connector inside the new event loop
        # because asyncio.run() creates a fresh loop, and the global _async_connector
        # is bound to the main loop.
        import threading

        def _run_extraction():
            import asyncio

            async def _extract():
                # Create fresh Cloud SQL async connector inside this event loop
                from google.cloud.sql.connector import IPTypes, create_async_connector
                from sqlalchemy import text
                from sqlalchemy.ext.asyncio import (
                    AsyncSession,
                    async_sessionmaker,
                    create_async_engine,
                )

                # Create connector bound to THIS event loop
                connector = await create_async_connector()

                async def getconn():
                    return await connector.connect_async(
                        settings.CLOUD_SQL_CONNECTION_NAME,
                        "asyncpg",
                        user=settings.DB_USER,
                        password=settings.DB_PASS,
                        db=settings.DB_NAME,
                        ip_type=IPTypes.PUBLIC,
                    )

                engine = create_async_engine(
                    "postgresql+asyncpg://",
                    async_creator=getconn,
                    pool_size=1,
                    max_overflow=0,
                )
                async_session = async_sessionmaker(
                    bind=engine, class_=AsyncSession, expire_on_commit=False
                )

                try:
                    async with async_session() as db:
                        # Set RLS context
                        await db.execute(
                            text(
                                "SELECT set_config('app.current_org_id', :org_id, false)"
                            ),
                            {"org_id": org_id},
                        )
                        await process_document_extraction(doc_id, org_id, db)
                except Exception as e:
                    logger.error(f"[LOCAL] Extraction failed for doc {doc_id}: {e}")
                    raise
                finally:
                    await engine.dispose()
                    await connector.close_async()

            asyncio.run(_extract())

        thread = threading.Thread(target=_run_extraction, daemon=True)
        thread.start()
        logger.info(f"[LOCAL] Started extraction thread for document {doc_id}")
        return

    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH

        # Construct the request body
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/api/v1/tasks/process-document",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.CLOUD_RUN_AUDIENCE_URL,  # Use Cloud Run URL, not custom domain
                },
                "body": json.dumps(
                    {"document_id": str(doc_id), "organization_id": org_id}
                ).encode(),
            }
        }

        logger.info(f"🚀 Enqueuing extraction task for doc {doc_id} to {parent}")
        logger.info(f"🔑 OIDC Audience: {settings.CLOUD_RUN_AUDIENCE_URL}")

        # ACTUAL ENQUEUE
        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"Task created: {response.name}")

    except Exception as e:
        logger.error(f"Failed to enqueue extraction task for doc {doc_id}: {e}")
        # Re-raise to propagate error to caller
        # Cloud Tasks workers will retry; API endpoints will return error to user
        raise


def trigger_case_processing_task(case_id: str, org_id: str):
    """
    Enqueues a task to Cloud Tasks to process the full case (dispatch documents).
    """
    if settings.RUN_LOCALLY:
        # Local dev: run case processing in background thread
        # CRITICAL: Create fresh async connector inside new event loop
        import threading

        def _run_processing():
            import asyncio

            async def _process():
                # Create fresh Cloud SQL async connector inside this event loop
                from google.cloud.sql.connector import IPTypes, create_async_connector
                from sqlalchemy import text
                from sqlalchemy.ext.asyncio import (
                    AsyncSession,
                    async_sessionmaker,
                    create_async_engine,
                )

                from app.services import report_generation_service

                connector = await create_async_connector()

                async def getconn():
                    return await connector.connect_async(
                        settings.CLOUD_SQL_CONNECTION_NAME,
                        "asyncpg",
                        user=settings.DB_USER,
                        password=settings.DB_PASS,
                        db=settings.DB_NAME,
                        ip_type=IPTypes.PUBLIC,
                    )

                engine = create_async_engine(
                    "postgresql+asyncpg://",
                    async_creator=getconn,
                    pool_size=1,
                    max_overflow=0,
                )
                async_session_factory = async_sessionmaker(
                    bind=engine, class_=AsyncSession, expire_on_commit=False
                )

                try:
                    async with async_session_factory() as db:
                        await db.execute(
                            text(
                                "SELECT set_config('app.current_org_id', :org_id, false)"
                            ),
                            {"org_id": org_id},
                        )
                        await report_generation_service.process_case_logic(
                            case_id, org_id, db
                        )
                except Exception as e:
                    logger.error(f"[LOCAL] Case processing failed for {case_id}: {e}")
                    raise
                finally:
                    await engine.dispose()
                    await connector.close_async()

            asyncio.run(_process())

        thread = threading.Thread(target=_run_processing, daemon=True)
        thread.start()
        logger.info(f"[LOCAL] Started case processing thread for case {case_id}")
        return

    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/api/v1/tasks/process-case",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.CLOUD_RUN_AUDIENCE_URL,  # Use Cloud Run URL, not custom domain
                },
                "body": json.dumps(
                    {"case_id": str(case_id), "organization_id": org_id}
                ).encode(),
            }
        }

        logger.info(f"🚀 Enqueuing case processing task for case {case_id}")
        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"Task created: {response.name}")

    except Exception:
        # Re-raise to propagate error to caller (API endpoint returns HTTP error)
        raise


def trigger_client_enrichment_task(client_id: str, original_name: str):
    """
    Enqueue async enrichment task via Cloud Tasks (or run locally for dev).

    ICE (Intelligent Client Enrichment) feature.
    Called when a NEW client is created during case creation.
    """
    if settings.RUN_LOCALLY:
        # Local dev: run in background thread to avoid blocking
        import asyncio
        import threading

        from app.db.database import SessionLocal
        from app.services.enrichment_service import EnrichmentService

        def _run_enrichment():
            async def _enrich():
                service = EnrichmentService()
                with SessionLocal() as db:
                    await service.enrich_and_update_client(client_id, original_name, db)

            asyncio.run(_enrich())

        thread = threading.Thread(target=_run_enrichment, daemon=True)
        thread.start()
        logger.info(
            f"[LOCAL] Started enrichment thread for client {client_id} ('{original_name}')"
        )
        return

    # Production: Cloud Tasks
    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/api/v1/tasks/enrich-client",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.CLOUD_RUN_AUDIENCE_URL,
                },
                "body": json.dumps(
                    {"client_id": client_id, "original_name": original_name}
                ).encode(),
            }
        }

        logger.info(
            f"🧠 Enqueuing ICE enrichment task for client {client_id} ('{original_name}')"
        )
        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"ICE task created: {response.name}")

    except Exception as e:
        # Don't fail case creation if enrichment task fails - it's a nice-to-have
        logger.error(
            f"Failed to enqueue ICE enrichment task for client {client_id}: {e}"
        )


def trigger_case_details_extraction_task(
    case_id: str,
    organization_id: str,
    final_docx_path: str,
    overwrite_existing: bool = False,
) -> None:
    """
    Enqueue async task to extract case details from final report.

    Called AFTER case finalization (after db.commit()) to populate CaseDetailsPanel.
    Uses gemini-2.0-flash-lite-001 for cost-effective extraction.
    """
    if settings.RUN_LOCALLY:
        # Local dev: run in background thread (like ICE enrichment)
        import threading

        from app.services.case_details_extractor import run_extraction_sync

        def _run() -> None:
            run_extraction_sync(
                case_id=case_id,
                org_id=organization_id,
                final_docx_path=final_docx_path,
                overwrite_existing=overwrite_existing,
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        logger.info(f"[LOCAL] Started case details extraction thread for {case_id}")
        return

    # Production: Cloud Tasks
    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/api/v1/tasks/extract-case-details",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.CLOUD_RUN_AUDIENCE_URL,
                },
                "body": json.dumps(
                    {
                        "case_id": case_id,
                        "organization_id": organization_id,
                        "final_docx_path": final_docx_path,
                        "overwrite_existing": overwrite_existing,
                    }
                ).encode(),
            }
        }

        logger.info(f"📊 Enqueuing case details extraction task for case {case_id}")
        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"Case details extraction task created: {response.name}")

    except Exception as e:
        # Don't fail finalization if extraction task fails - case is already saved
        logger.error(
            f"Failed to enqueue case details extraction task for {case_id}: {e}"
        )


async def run_process_document_extraction_standalone(doc_id: UUID, org_id: str):
    """
    Wrapper for background execution that manages its own ASYNC DB session.
    Used by Cloud Tasks to process documents safely without sharing sessions across threads.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Set RLS context for the background session (async style)
            await db.execute(
                text("SELECT set_config('app.current_org_id', :org_id, false)"),
                {"org_id": org_id},
            )

            await process_document_extraction(doc_id, org_id, db)
        except Exception as e:
            logger.error(f"Async extraction task failed: {e}")
            await db.rollback()
            raise


async def process_document_extraction(doc_id: UUID, org_id: str, db: AsyncSession):
    """
    Actual logic to process the document (Download -> Extract -> Save).
    """

    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalars().first()
    if not doc:
        return

    # FIX: Idempotency Check - Skip extraction if already processed
    # This prevents expensive re-downloads and re-extractions on Cloud Tasks retries
    if doc.ai_status == ExtractionStatus.SUCCESS.value:
        logger.info(
            f"Document {doc.id} already processed. Skipping extraction, proceeding to Fan-In check."
        )
        # Skip to Fan-In check at the end of this function
    else:
        # Perform extraction only if not already processed
        tmp_dir = tempfile.mkdtemp()
        try:
            async with extraction_semaphore:
                # Run core logic in thread pool to avoid blocking event loop
                await asyncio.to_thread(_perform_extraction_logic, doc, tmp_dir)

            # 3. Save to DB
            doc.ai_status = ExtractionStatus.SUCCESS
            await db.commit()
            logger.info(f"Extraction complete for {doc.id}")

        except Exception as e:
            logger.error(f"Error extracting document {doc.id}: {e}")
            doc.ai_status = ExtractionStatus.ERROR
            doc.error_message = _get_user_friendly_error(str(e))
            await db.commit()
        finally:
            shutil.rmtree(tmp_dir)

    # Auto-generation disabled: User must click "Genera con IA" to trigger report.
    logger.info(f"Document {doc.id} extraction complete. Awaiting user action.")


def _perform_extraction_logic(doc: Document, tmp_dir: str):
    """
    Core extraction logic: Download -> Extract -> Upload Artifacts.
    This function is SYNCHRONOUS and blocking.

    OPTIMIZATION: Vision files (PDF/images) skip download since LLM reads
    directly from GCS at generation time.
    """
    import time
    start_time = time.perf_counter()

    # Check if file is vision-only (PDF/images)
    ext = os.path.splitext(doc.filename)[1].lower()
    VISION_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}

    if ext in VISION_EXTS:
        # FAST PATH: Vision files don't need local extraction
        # LLM reads directly from GCS via Part.from_uri() at generation time
        logger.info(f"⚡ Fast path: {doc.filename} (vision-only, skipping GCS download)")

        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }

        doc.ai_extracted_data = [
            {
                "type": "vision",
                "path": None,  # Not used - LLM uses gcs_path
                "gcs_path": doc.gcs_path,
                "mime_type": mime_map.get(ext, "application/octet-stream"),
                "filename": doc.filename,
            }
        ]

        logger.info(f"📊 {doc.filename}: {time.perf_counter() - start_time:.3f}s (fast path)")
        return

    # STANDARD PATH: Text files (DOCX, XLSX, TXT, EML) need local processing
    # 1. Download
    download_start = time.perf_counter()
    local_filename = f"extract_{doc.id}_{doc.filename}"
    local_path = os.path.join(tmp_dir, local_filename)

    logger.info(f"Downloading {doc.gcs_path} for extraction...")
    download_file_to_temp(doc.gcs_path, local_path)
    download_duration = time.perf_counter() - download_start

    # 2. Extract
    extract_start = time.perf_counter()
    logger.info(f"Extracting text from {local_filename}...")
    processed = document_processor.process_uploaded_file(local_path, tmp_dir)
    extract_duration = time.perf_counter() - extract_start

    # --- Persist extracted artifacts to GCS ---
    storage_client = get_storage_client()
    bucket_name = settings.STORAGE_BUCKET_NAME
    bucket = storage_client.bucket(bucket_name)

    for item in processed:
        item_path = item.get("path")
        if item_path and item_path != local_path and os.path.exists(item_path):
            artifact_filename = os.path.basename(item_path)
            blob_name = f"uploads/{doc.organization_id}/{doc.case_id}/artifacts/{doc.id}_{artifact_filename}"

            logger.info(f"Uploading extracted artifact {artifact_filename} to GCS...")

            blob = bucket.blob(blob_name)
            blob.upload_from_filename(item_path)

            item["item_gcs_path"] = f"gs://{bucket_name}/{blob_name}"

    # Update doc object (in memory, caller saves to DB)
    doc.ai_extracted_data = processed  # type: ignore[assignment]

    total_duration = time.perf_counter() - start_time
    logger.info(
        f"📊 {doc.filename}: download={download_duration:.2f}s, "
        f"extract={extract_duration:.2f}s, total={total_duration:.2f}s"
    )


async def _check_and_trigger_generation(
    db: AsyncSession, case_id: UUID, org_id: str, is_async: bool = True
):
    """
    Checks if all documents are processed and triggers generation if so.
    """
    try:
        # Lock the Case immediately
        result = await db.execute(
            select(Case).filter(Case.id == case_id).with_for_update()
        )
        case = result.scalars().first()

        # Null check for case
        if not case:
            logger.warning(f"Case {case_id} not found for generation check.")
            return

        # Check if we are already generating to fail fast
        if case.status == CaseStatus.GENERATING:
            logger.info(
                f"Case {case_id} is already generating. Skipping completion check."
            )
            return

        # Re-query all docs inside this locked transaction
        from sqlalchemy import func

        # PERFORMANCE FIX: Count pending docs instead of loading objects
        # This is O(1) memory vs O(N)
        stmt = (
            select(func.count())
            .select_from(Document)
            .filter(
                Document.case_id == case_id,
                Document.ai_status.notin_(
                    [
                        ExtractionStatus.SUCCESS.value,
                        ExtractionStatus.ERROR.value,
                        ExtractionStatus.SKIPPED.value,
                    ]
                ),
            )
        )
        pending_count = await db.scalar(stmt)

        if pending_count == 0:
            logger.info(
                f"All documents for case {case_id} finished. Triggering generation."
            )

            # CRITICAL: Set status here to prevent other workers from entering
            # ZOMBIE STATE RACE CONDITION MITIGATION:
            # We use the Transactional Outbox Pattern.
            # 1. Update Case Status
            # 2. Insert Intent into Outbox (Same Transaction)
            # 3. Atomic Commit

            try:
                # 1. Update Case Status
                case.status = CaseStatus.GENERATING

                # 2. Insert Intent into Outbox (Same Transaction)
                from app.models.outbox import OutboxMessage

                outbox_entry = OutboxMessage(
                    topic="generate_report",
                    organization_id=(
                        UUID(org_id) if isinstance(org_id, str) else org_id
                    ),
                    payload={
                        "case_id": str(case_id),
                        "organization_id": org_id,
                    },
                )
                db.add(outbox_entry)

                # 3. Atomic Commit
                # If this fails, BOTH the status update and the message insert are rolled back.
                # No Zombie state is possible.
                await db.commit()

                # 4. Attempt Immediate Dispatch (Best Effort / Optimization)
                # We try to send it now for speed. If this fails, the background poller will catch it.
                if is_async:
                    try:
                        from app.services.outbox_processor import process_message

                        await process_message(outbox_entry.id, db)
                    except Exception as e:
                        logger.warning(
                            f"Immediate dispatch failed (will retry via cron): {e}"
                        )
                        # Do NOT re-raise. The data is safe in the DB.
                else:
                    # For sync path, we skip immediate dispatch and rely on the poller
                    # because process_message is async.
                    logger.info(
                        "Skipping immediate dispatch in sync mode (will be picked up by poller)"
                    )

            except Exception as e:
                await db.rollback()
                logger.error(f"Error checking case completion: {e}")
                raise e

    except Exception as e:
        # Rollback in case of error during the lock/check
        await db.rollback()
        logger.error(f"Error checking case completion: {e}")
        # Re-raise to ensure Cloud Tasks retries
        raise e


def _get_user_friendly_error(raw_error: str) -> str:
    """Mappa errori tecnici a messaggi comprensibili per l'utente."""
    ERROR_MAP = {
        "BadZipFile": "File corrotto: il documento non è valido",
        "FileDataError": "PDF corrotto: impossibile leggere il file",
        "InvalidFileException": "Excel corrotto: formato non valido",
        "UnicodeDecodeError": "Codifica testo non supportata",
        "UnidentifiedImageError": "Immagine corrotta o formato non riconosciuto",
        "MemoryError": "File troppo grande per essere elaborato",
        "recursion": "Troppi allegati annidati nell'email",
        "too large": "File o allegato troppo grande",
        "Unsupported file type": "Tipo di file non supportato",
    }
    return next(
        (msg for key, msg in ERROR_MAP.items() if key.lower() in raw_error.lower()),
        "Errore durante l'elaborazione del documento",
    )
