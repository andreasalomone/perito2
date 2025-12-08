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

# NOTE: Phase 3 optimization removed the download step - we now use Part.from_uri() directly

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
            case_service.trigger_extraction_task(doc.id, organization_id)
    
    # NOTE: We do NOT auto-trigger generation here.
    # Users must explicitly click "Genera con IA" when ready.

    # Reset status back to OPEN after dispatching all tasks
    # The PROCESSING status was set to prevent duplicate dispatch attempts (race condition guard).
    # Now that dispatch is complete, the case should be OPEN while documents are processed.
    result = await db.execute(
        select(Case).filter(Case.id == case_id).with_for_update()
    )
    case = result.scalars().first()
    if case and case.status == CaseStatus.PROCESSING:
        case.status = CaseStatus.OPEN
        await db.commit()
        logger.info(f"Case {case_id} status reset to OPEN after dispatching document tasks")


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
                    "audience": settings.CLOUD_RUN_AUDIENCE_URL,  # Use Cloud Run URL, not custom domain
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

    # IDEMPOTENCY CHECK 2: Check if report exists in GCS but not in DB (partial failure recovery)
    # FIX BUG-3: This handles the case where upload succeeded but commit failed
    bucket_name = settings.STORAGE_BUCKET_NAME
    expected_blob_name = f"reports/{organization_id}/{case_id}/v1_AI_Draft.docx"
    
    try:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(expected_blob_name)
        gcs_path_exists = await asyncio.to_thread(blob.exists)
        
        if gcs_path_exists:
            logger.warning(
                f"Found orphaned report in GCS for case {case_id}. "
                f"Recovering by creating DB record without regenerating."
            )
            # Create DB record pointing to existing GCS file (saves $0.50-$2.00 API call)
            v1 = ReportVersion(
                case_id=case_id,
                organization_id=organization_id,
                version_number=1,
                docx_storage_path=f"gs://{bucket_name}/{expected_blob_name}",
                ai_raw_output="[Recovered from GCS - original AI output not available]",
                is_final=False
            )
            db.add(v1)
            case.status = CaseStatus.OPEN
            await db.commit()
            logger.info(f"✅ Recovered orphaned report for case {case_id}")
            return
    except Exception as e:
        logger.warning(f"Could not check GCS for existing report: {e}. Proceeding with generation.")
        # Continue with normal generation if GCS check fails

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
    # NOTE: Phase 3 optimization removed temp file downloads - GCS direct access via Part.from_uri()
    
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
                # FIX BUG-5: Deep copy the data to prevent mutating the SQLAlchemy object
                # DEFENSIVE: Store original reference for assertion
                original_data_id = id(doc.ai_extracted_data)
                data = copy.deepcopy(doc.ai_extracted_data)
                copied_data_id = id(data)
                
                # Assertion: Verify deep copy created new object
                assert original_data_id != copied_data_id, (
                    f"Deep copy failed for document {doc.id}. "
                    f"Original and copy have same memory address."
                )
                
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
                            # Phase 3 Optimization: llm_handler uses Part.from_uri() directly
                            # so NO download is needed here anymore.
                            item["gcs_uri"] = target_gcs_path
                            item["local_path"] = None  # No local file needed
                            logger.debug(f"Using GCS direct access for {item.get('filename', 'asset')}: {target_gcs_path}")
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
        
        # FIX BUG-6: Defensive check with proper error signaling
        if not case:
            error_msg = (
                f"Case {case_id} disappeared during generation. "
                f"Likely deleted manually. Marking as permanent failure."
            )
            logger.error(error_msg)
            # Raise exception to signal to Cloud Tasks that this is unrecoverable
            # This prevents infinite retries
            raise ValueError(error_msg)
             
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
        
        # 6. Generate Summary (non-blocking - failures don't affect main report)
        try:
            from app.services import summary_service
            summary = await summary_service.generate_summary(report_text)
            if summary:
                case.ai_summary = summary
                await db.commit()
                logger.info(f"✅ Summary generated for case {case_id}")
        except Exception as e:
            logger.warning(f"⚠️ Summary generation failed (non-critical): {e}")

    except Exception as e:
        logger.error(f"❌ Error during generation: {e}", exc_info=True)
        # Re-acquire lock to set error state
        try:
            # FIX: Rollback any failed transaction state before starting new query
            # This ensures we can update the status even if the error was a DB error
            await db.rollback() 
            
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
        #
        # [COST SAFEGUARD] MANUAL RETRY WORKFLOW
        # We explicitly catch and swallow the error here to STOP Cloud Tasks from 
        # retrying indefinitely (or up to 100 times).
        # The user must manually click "Retry" in the UI.
        
        logger.critical(f"🛑 Stopping Cloud Task retry loop for case {case_id} due to error: {e}")
        return # Return success to Cloud Tasks so it marks the task as completed.
    finally:
        pass  # Phase 3 optimization removed temp file cleanup - no longer needed

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
    # Use gcs_service helper which handles IAM SignBlob for Cloud Run
    from app.services.gcs_service import generate_download_signed_url
    gcs_path = f"gs://{bucket_name}/{blob_name}"
    url = generate_download_signed_url(gcs_path)
    
    return url


