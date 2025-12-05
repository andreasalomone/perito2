import os
import tempfile
import copy
import uuid

import pathlib
import asyncio
import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from uuid import UUID
from google.cloud import tasks_v2
from sqlalchemy.exc import IntegrityError

from app.models import Case, Document, ReportVersion
from app.schemas.enums import ExtractionStatus, CaseStatus
from app.services.gcs_service import get_storage_client, download_file_to_temp
from app.core.config import settings
from app.services import document_processor, llm_handler, docx_generator, case_service
from app.services.llm_handler import gemini_generator, ProcessedFile
from app.db.database import AsyncSessionLocal

import threading

logger = logging.getLogger(__name__)

# Limit concurrent downloads during generation to prevent filling up memory/disk
download_semaphore = threading.Semaphore(5)

async def run_generation_task(case_id: str, organization_id: str):
    """
    Wrapper for background execution that manages its own ASYNC DB session.
    Uses AsyncSessionLocal for proper async database operations.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Set RLS context for the background session (async style)
            await db.execute(
                text("SELECT set_config('app.current_org_id', :org_id, false)"), 
                {"org_id": organization_id}
            )
            
            await generate_report_logic(case_id, organization_id, db)
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
                {"org_id": organization_id}
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
    result = await db.execute(
        select(Case).filter(Case.id == case_id).with_for_update()
    )
    case = result.scalars().first()
    if not case:
        logger.error(f"Case {case_id} not found in DB")
        return

    # DUPLICATE PREVENTION: Check if already processing (now atomic with lock)
    if case.status == CaseStatus.PROCESSING:
        logger.warning(f"Case {case_id} already processing, skipping duplicate dispatch")
        return

    # Update status to processing
    case.status = CaseStatus.PROCESSING
    await db.commit()

    # 2. Fetch Documents
    result = await db.execute(
        select(Document).filter(Document.case_id == case_id)
    )
    documents = result.scalars().all()
    if not documents:
        logger.warning(f"No documents found for case {case_id}")
        return

    # 3. Dispatch Tasks
    all_processed = True
    for doc in documents:
        if doc.ai_status == ExtractionStatus.SUCCESS:
            continue
            
        all_processed = False
        
        # For local dev, process inline instead of dispatching tasks
        if settings.RUN_LOCALLY:
            logger.info(f"Local mode: Processing document {doc.id} inline")
            await case_service.process_document_extraction(doc.id, organization_id, db)
        else:
            # Dispatch Cloud Task
            case_service.trigger_extraction_task(doc.id, organization_id)
        
    # 4. Optimization: If all were already processed (e.g. retry), trigger generation immediately
    if all_processed:
        logger.info(f"All documents for case {case_id} already processed. Triggering generation immediately.")
        await trigger_generation_task(case_id, organization_id)


async def trigger_generation_task(case_id: str, organization_id: str):
    """
    Enqueues the 'generate-report' task.
    """
    if settings.RUN_LOCALLY:
        logger.info(f"Running generation locally for case {case_id}")
        # Run in background (fire and forget) or await if we want to block
        # Since this is usually called from a task or API, we can just run it.
        # But we need a fresh DB session if we run it directly.
        await run_generation_task(case_id, organization_id)
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
                    "audience": settings.RESOLVED_BACKEND_URL,
                },
                "body": json.dumps({
                    "case_id": str(case_id),
                    "organization_id": organization_id
                }).encode()
            }
        }
        
        logger.info(f"🚀 Enqueuing generation task for case {case_id}")
        client.create_task(request={"parent": parent, "task": task})
        
    except Exception as e:
        logger.error(f"Failed to enqueue generation task for case {case_id}: {e}")
        # Re-raise to propagate error
        # This allows document workers to retry completion check
        raise


async def generate_report_logic(case_id: str, organization_id: str, db: AsyncSession):
    """
    Phase 2: Generation
    Called when all documents are processed.
    1. Aggregates data.
    2. Generates AI Report.
    3. Creates Version 1.
    """
    # 1. Fetch case
    result = await db.execute(
        select(Case).filter(Case.id == case_id).with_for_update()
    )
    case = result.scalars().first()
    if not case:
        logger.error(f"Case {case_id} not found")
        return

    # DUPLICATE GENERATION PREVENTION: Check if already generating or done
    # Note: We removed the check for 'generating' because case_service now sets this status 
    # BEFORE triggering the task to prevent race conditions. If we check it here, 
    # the valid task would abort itself.
    # We rely on case_service's strict locking to ensure only one task is triggered.

    # IDEMPOTENCY CHECK: Check if report already exists
    result = await db.execute(
        select(ReportVersion).filter(
            ReportVersion.case_id == case_id,
            ReportVersion.version_number == 1
        )
    )
    existing_report = result.scalars().first()
    
    if existing_report:
        logger.info(f"Report for case {case_id} already exists. Aborting duplicate generation.")
        # Ensure status is correct
        if case.status != CaseStatus.OPEN:
            case.status = CaseStatus.OPEN
            await db.commit()
        return

    # Set granular status
    case.status = CaseStatus.GENERATING
    await db.commit()

    # --- INVARIANT CHECK ---
    # Re-fetch documents to get latest status
    result = await db.execute(
        select(Document).filter(Document.case_id == case_id)
    )
    all_docs = result.scalars().all()
    
    # Check if all documents are processed
    pending_docs = [d for d in all_docs if d.ai_status not in [ExtractionStatus.SUCCESS.value, ExtractionStatus.ERROR.value, ExtractionStatus.SKIPPED.value]]
    if pending_docs:
        logger.info(f"Case {case_id} has pending documents: {[d.id for d in pending_docs]}. Skipping generation.")
        return
    
    # Check if we have at least one processed document
    has_completed_docs = any(d.ai_status == ExtractionStatus.SUCCESS.value for d in all_docs)
    if not has_completed_docs:
        logger.error(f"Cannot generate report for case {case_id}: No successfully processed documents found (all failed or empty).")
        case.status = CaseStatus.ERROR
        await db.commit()
        # STOP RETRIES: Return gracefully as this is an unrecoverable data state.
        # Raising an error would cause Cloud Tasks to retry indefinitely.
        return

    processed_count = sum(1 for d in all_docs if d.ai_status == ExtractionStatus.SUCCESS.value)
    error_count = sum(1 for d in all_docs if d.ai_status == ExtractionStatus.ERROR)
    logger.info(f"Starting generation for case {case_id} with {processed_count} processed and {error_count} failed documents.")
    
    # CRITICAL FIX: Release the lock before starting long-running AI operations.
    # This prevents DB connection starvation and deadlocks.
    await db.commit()

    processed_data_for_llm = []
    failed_docs = []  # Track failed documents for user visibility
    temp_files_to_cleanup: list[str] = []  # Track temp files for cleanup
    
    try:
        # 1. Fetch Processed Data (Re-query as we released the session)
        # Note: We don't need a lock here as we are just reading data for the prompt.
        result = await db.execute(
            select(Document).filter(Document.case_id == case_id)
        )
        documents = result.scalars().all()
        if documents:
             pass
        for doc in documents:
            if doc.ai_status == ExtractionStatus.SUCCESS.value and doc.ai_extracted_data:
                # FIX: Deep copy the data to prevent mutating the SQLAlchemy object
                data = copy.deepcopy(doc.ai_extracted_data)
                if isinstance(data, dict):
                    data = [data]
                
                # Update items with GCS URI for on-demand processing
                for item in data:
                    if item.get("type") == "vision":
                        # Check if this specific item has its own GCS path (Artifact)
                        # Fallback to the Document's main GCS path (Original)
                        target_gcs_path = item.get("item_gcs_path") or doc.gcs_path

                        if target_gcs_path:
                            # Pass the GCS URI to the LLM handler.
                            # The file_upload_service will handle downloading it on-demand
                            # to a temp file, uploading to Gemini, and cleaning up.
                            # This prevents loading all files into disk/RAM at once.
                            item["gcs_uri"] = target_gcs_path
                            item["local_path"] = None # Ensure we don't rely on stale local paths
                            try:
                                logger.info(f"Re-downloading {target_gcs_path} for generation...")
                                with download_semaphore:
                                    # Use the helper that handles gs:// parsing
                                    # [FIX] Generate a valid temp path
                                    fd, local_path = tempfile.mkstemp(suffix=f"_{item.get('filename', 'asset')}")
                                    os.close(fd) # Close the file descriptor immediately
                                    temp_files_to_cleanup.append(local_path)  # Track for cleanup
                                    
                                    item["local_path"] = local_path # Update the dict
                                    
                                    await asyncio.to_thread(download_file_to_temp, target_gcs_path, local_path)
                            except Exception as e:
                                logger.error(f"Failed to re-download {target_gcs_path} for generation: {e}")
                                item["type"] = "error"
                                item["error"] = f"Failed to download: {e}"
                        else:
                            logger.warning(f"Item {item.get('filename', 'unknown')} has no GCS source.")
                            item["type"] = "error"
                            item["error"] = "Missing GCS source path"
                
                processed_data_for_llm.extend(data)
            elif doc.ai_status == ExtractionStatus.ERROR:
                # Track failed docs with reason
                failed_docs.append({
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "reason": "Processing failed"
                })
                logger.warning(f"Document {doc.id} ({doc.filename}) failed processing - skipping")
            else:
                # Document still pending or other status
                failed_docs.append({
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "reason": f"Status: {doc.ai_status}"
                })
                logger.warning(f"Document {doc.id} ({doc.filename}) is not processed (Status: {doc.ai_status}). Skipping.")

        if not processed_data_for_llm:
            logger.error("No processed data available for generation.")
            raise ValueError("No processed data found")
        
        # Log summary of what we're generating with
        total_docs = len(documents)
        processed_docs = len(processed_data_for_llm)
        failed_count = len(failed_docs)
        logger.info(f"Generating report from {processed_docs}/{total_docs} documents ({failed_count} failed/skipped)")
        if failed_docs:
            logger.warning(f"Failed documents: {[d['filename'] for d in failed_docs]}")

        # 2. Generate with Gemini
        logger.info("Generating text with Gemini...")
        
        # Convert dicts to Pydantic models
        processed_files_models = [ProcessedFile(**item) for item in processed_data_for_llm]
        
        report_result = await gemini_generator.generate(
            processed_files=processed_files_models
        )
        report_text = report_result.content
        token_usage = report_result.usage.model_dump()

        # 3. Generate DOCX
        logger.info("Generating DOCX...")
        docx_stream = await asyncio.to_thread(docx_generator.create_styled_docx, report_text)
        
        # 4. Upload Result
        bucket_name = settings.STORAGE_BUCKET_NAME
        blob_name = f"reports/{organization_id}/{case_id}/v1_AI_Draft.docx"
        
        def upload_blob():
            storage_client = get_storage_client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(docx_stream, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            return f"gs://{bucket_name}/{blob_name}"

        final_docx_path = await asyncio.to_thread(upload_blob)

        # 5. Save Version 1
        # Re-acquire Lock to save the result safely
        result = await db.execute(
            select(Case).filter(Case.id == case_id).with_for_update()
        )
        case = result.scalars().first()
        
        # Defensive: Check if state changed while we were away (e.g. user cancelled, or error)
        if not case:
             logger.error(f"Case {case_id} disappeared during generation.")
             return
             
        if case.status == CaseStatus.ERROR:
             logger.warning("Case marked as error by another process during generation. Overwriting with success.")
        
        result = await db.execute(
            select(ReportVersion).filter(
                ReportVersion.case_id == case_id, 
                ReportVersion.version_number == 1
            )
        )
        v1 = result.scalars().first()
        
        if not v1:
            v1 = ReportVersion(
                case_id=case_id,
                organization_id=organization_id,
                version_number=1,
                docx_storage_path=final_docx_path,
                ai_raw_output=report_text,
                is_final=False
            )
            db.add(v1)
        else:
            v1.docx_storage_path = final_docx_path
            v1.ai_raw_output = report_text
            
        case.status = CaseStatus.OPEN
        try:
            await db.commit()
            logger.info("✅ Case processing completed successfully. Version 1 created.")
        except IntegrityError:
            await db.rollback()
            logger.error(f"IntegrityError saving Version 1 for case {case_id}. Likely race condition.")
            raise

    except Exception as e:
        logger.error(f"❌ Error during generation: {e}", exc_info=True)
        # Re-acquire lock to set error state
        try:
            result = await db.execute(
                select(Case).filter(Case.id == case_id).with_for_update()
            )
            case = result.scalars().first()
            if case:
                case.status = CaseStatus.ERROR
                await db.commit()
        except Exception as db_e:
            logger.error(f"Failed to update case status to error: {db_e}")
            
        # Don't raise if we want to swallow the error in the task worker,
        # but usually we want to raise so Cloud Tasks might retry (if transient)
        # For logic errors, maybe don't retry.
        # Let's raise for now.
        raise e
    finally:
        # CRITICAL: Clean up temp files to prevent memory exhaustion on Cloud Run
        # On Cloud Run Gen 2, /tmp is an in-memory filesystem (tmpfs)
        for temp_path in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file {temp_path}: {cleanup_error}")

async def generate_docx_variant(
    version_id: str, 
    template_type: str, 
    db: Session
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
    else:
        raise ValueError("Invalid template type")

    # 3. Generate DOCX
    logger.info(f"Generating DOCX variant {template_type} for version {version_id}...")
    docx_stream = await asyncio.to_thread(generator.create_styled_docx, version.ai_raw_output)

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
        if hasattr(docx_stream, 'seek'):
            docx_stream.seek(0)
        blob.upload_from_file(docx_stream, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        return blob

    blob = await asyncio.to_thread(upload_blob)
    
    # 5. Generate Signed URL (Read)
    # We can use the blob object directly or the gcs_service helper
    url = blob.generate_signed_url(
        version="v4",
        expiration=3600, # 1 hour
        method="GET"
    )
    
    return url


