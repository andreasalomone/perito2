import os
import uuid
import shutil
import tempfile
import pathlib
import asyncio
import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID
from google.cloud import tasks_v2

from app.models import Case, Document, ReportVersion
from app.services.gcs_service import get_storage_client, download_file_to_temp
from app.core.config import settings
from app.services import document_processor, llm_handler, docx_generator, case_service
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

# Limit concurrent downloads during generation to prevent filling up memory/disk
download_semaphore = asyncio.Semaphore(5)

async def run_generation_task(case_id: str, organization_id: str):
    """
    Wrapper for background execution that manages its own DB session.
    Now calls generate_report_logic instead of process_case_logic.
    """
    db = SessionLocal()
    try:
        await generate_report_logic(case_id, organization_id, db)
    finally:
        db.close()

async def process_case_logic(case_id: str, organization_id: str, db: Session):
    """
    Phase 1: Dispatch Tasks
    Iterates all documents and dispatches a 'process-document' Cloud Task for each.
    """
    # 1. Setup - Get Case with locking to prevent race conditions
    case = db.query(Case).filter(Case.id == case_id).with_for_update().first()
    if not case:
        logger.error(f"Case {case_id} not found in DB")
        return

    # DUPLICATE PREVENTION: Check if already processing (now atomic with lock)
    if case.status == "processing":
        logger.warning(f"Case {case_id} already processing, skipping duplicate dispatch")
        return

    # Update status to processing
    case.status = "processing"
    db.commit()

    # 2. Fetch Documents
    documents = db.query(Document).filter(Document.case_id == case_id).all()
    if not documents:
        logger.warning(f"No documents found for case {case_id}")
        return

    # 3. Dispatch Tasks
    all_processed = True
    for doc in documents:
        if doc.ai_status == "processed":
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
                "url": f"{settings.RESOLVED_BACKEND_URL}/tasks/generate-report",
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


async def generate_report_logic(case_id: str, organization_id: str, db: Session):
    """
    Phase 2: Generation
    Called when all documents are processed.
    1. Aggregates data.
    2. Generates AI Report.
    3. Creates Version 1.
    """
    # Lock case early to prevent duplicate generation
    case = db.query(Case).filter(Case.id == case_id).with_for_update().first()
    if not case:
        logger.error(f"Case {case_id} not found")
        return

    # DUPLICATE GENERATION PREVENTION: Check if already generating or done
    if case.status in ["generating", "open"]:
        logger.info(f"Case {case_id} already in status '{case.status}', aborting duplicate generation")
        return

    # Set granular status
    case.status = "generating"
    db.commit()

    # --- INVARIANT CHECK ---
    # Re-fetch documents to get latest status
    all_docs = db.query(Document).filter(Document.case_id == case_id).all()
    
    # 1. Check if all documents are in a terminal state (processed or error)
    # We don't want to generate if some are still "pending" or "processing"
    pending_docs = [d for d in all_docs if d.ai_status not in ["processed", "error"]]
    if pending_docs:
        logger.warning(f"Cannot generate report for case {case_id}: {len(pending_docs)} documents are still pending/processing.")
        # Revert status to processing so it can be retried later
        case.status = "processing"
        db.commit()
        return

    # 2. Check if we have AT LEAST ONE successfully processed document
    has_completed_docs = any(d.ai_status == "processed" for d in all_docs)
    if not has_completed_docs:
        logger.error(f"Cannot generate report for case {case_id}: No successfully processed documents found (all failed or empty).")
        case.status = "error"
        db.commit()
        # We raise an error so the task might be retried or logged as failure in Cloud Tasks
        raise ValueError("No valid documents to generate report from")

    # Log the state
    processed_count = sum(1 for d in all_docs if d.ai_status == "processed")
    error_count = sum(1 for d in all_docs if d.ai_status == "error")
    logger.info(f"Starting generation for case {case_id} with {processed_count} processed and {error_count} failed documents.")
    # -----------------------

    tmp_dir = tempfile.mkdtemp()
    processed_data_for_llm = []
    failed_docs = []  # Track failed documents for user visibility
    
    try:
        # 1. Fetch Processed Data
        documents = db.query(Document).filter(Document.case_id == case_id).all()
        for doc in documents:
            if doc.ai_status == "processed" and doc.ai_extracted_data:
                data = doc.ai_extracted_data
                if isinstance(data, dict):
                    data = [data]
                
                # Re-download files if needed (Vision API needs local files)
                # We do this here to ensure the file exists in the temp dir of THIS worker
                for item in data:
                    if item.get("type") == "vision":
                        # We need to re-download the file because the original temp file 
                        # from extraction might be gone (different worker / time passed)
                        # Construct local path in current tmp_dir
                        original_filename = item.get("filename", "unknown_file")
                        safe_filename = f"gen_{doc.id}_{original_filename}"
                        local_path = os.path.join(tmp_dir, safe_filename)
                        
                        # Use the GCS path from the document record
                        if doc.gcs_path:
                            try:
                                logger.info(f"Re-downloading {doc.gcs_path} for generation...")
                                async with download_semaphore:
                                    await asyncio.to_thread(download_file_to_temp, doc.gcs_path, local_path)
                                # Update the path in the item to point to the new local file
                                item["path"] = local_path
                            except Exception as e:
                                logger.error(f"Failed to re-download {doc.gcs_path}: {e}")
                                # If download fails, we might want to skip this item or fail the doc
                                # For now, let's mark as failed so we don't send bad path to Gemini
                                item["type"] = "error" 
                                item["error"] = f"Failed to download: {e}"
                        else:
                            logger.warning(f"Document {doc.id} has no GCS path, cannot re-download for vision.")
                
                processed_data_for_llm.extend(data)
            elif doc.ai_status == "error":
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
        report_text, token_usage = await llm_handler.generate_report_from_content(
            processed_files=processed_data_for_llm
        )

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
        # Lock Case to serialize
        db.query(Case).filter(Case.id == case_id).with_for_update().first()
        
        v1 = db.query(ReportVersion).filter(
            ReportVersion.case_id == case_id, 
            ReportVersion.version_number == 1
        ).first()
        
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
            
        case.status = "open"
        db.commit()
        logger.info("✅ Case processing completed successfully. Version 1 created.")

    except Exception as e:
        logger.error(f"❌ Error during generation: {e}", exc_info=True)
        case.status = "error"
        db.commit()
        # Don't raise if we want to swallow the error in the task worker, 
        # but usually we want to raise so Cloud Tasks might retry (if transient)
        # For logic errors, maybe don't retry.
        # Let's raise for now.
        raise e 
    finally:
        shutil.rmtree(tmp_dir)

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
