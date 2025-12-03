from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from app.models import Case, ReportVersion, MLTrainingPair, Document, Client
from app.core.config import settings
import logging
import json
import asyncio
from google.cloud import tasks_v2
import os
import tempfile
import shutil
from app.services import document_processor
from app.services.gcs_service import download_file_to_temp, get_storage_client

# Limit concurrent extractions to prevent filling up memory/disk
extraction_semaphore = asyncio.Semaphore(5)

logger = logging.getLogger(__name__)


from sqlalchemy.exc import IntegrityError

def get_or_create_client(db: Session, name: str, organization_id: UUID) -> Client:
    # 1. Try to find existing within this organization
    client = db.query(Client).filter(
        Client.name == name,
        Client.organization_id == organization_id
    ).first()
    if client:
        return client

    # 2. Try to create (Handle Race Condition with SAVEPOINT)
    # Verified by backend/tests/test_client_creation_race.py
    # Use begin_nested() to create a SAVEPOINT
    try:
        with db.begin_nested():
            client = Client(name=name, organization_id=organization_id)
            db.add(client)
            db.flush()  # Flush within the savepoint
        # If we get here, the savepoint was successful
        # Note: we don't commit here because we're inside a larger transaction
        db.flush()  # Make sure the client ID is available
        db.refresh(client)
        return client
        
    except IntegrityError:
        # Rollback happens automatically to the savepoint, not the whole transaction
        # Another process created the client, so fetch it
        return db.query(Client).filter(
            Client.name == name, 
            Client.organization_id == organization_id
        ).one()

# --- THE CRITICAL WORKFLOWS ---

def create_ai_version(db: Session, case_id: UUID, org_id: UUID, ai_text: str, docx_path: str):
    """
    Called by the Worker after Gemini finishes.
    Creates Version 1 (or next version).
    """
    # 0. LOCK the Case to prevent version race conditions
    # This ensures only one transaction can add a version at a time for this case.
    db.query(Case).filter(Case.id == case_id).with_for_update().first()

    # 1. Determine version number (Robust: Use MAX + 1, not COUNT)
    from sqlalchemy import func
    max_ver = db.query(func.max(ReportVersion.version_number)).filter(ReportVersion.case_id == case_id).scalar()
    next_version = (max_ver or 0) + 1
    
    # 2. Save Version
    version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=next_version,
        docx_storage_path=docx_path,
        ai_raw_output=ai_text,
        is_final=False
    )
    db.add(version)
    
    try:
        db.commit()
        return version
    except IntegrityError:
        db.rollback()
        # Retry logic or fail gracefully
        # Since we locked the case, this should rarely happen unless manual DB intervention
        logger.error(f"IntegrityError creating version {next_version} for case {case_id}")
        raise

def finalize_case(db: Session, case_id: UUID, org_id: UUID, final_docx_path: str):
    """
    Called when User uploads the final "signed" PDF/DOCX.
    1. Save new version.
    2. Mark as Final.
    3. Create ML Training Pair.
    """
    # 1. Create Final Version
    # LOCK the Case to prevent version race conditions
    db.query(Case).filter(Case.id == case_id).with_for_update().first()

    from sqlalchemy import func
    max_ver = db.query(func.max(ReportVersion.version_number)).filter(ReportVersion.case_id == case_id).scalar()
    next_version = (max_ver or 0) + 1

    final_version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=next_version,
        docx_storage_path=final_docx_path,
        is_final=True
    )
    db.add(final_version)
    try:
        db.flush() # Get ID
    except IntegrityError:
        db.rollback()
        logger.error(f"IntegrityError creating final version {next_version} for case {case_id}")
        raise
    
    # 2. Find the original AI Draft (Version 1 usually, or last AI version)
    # Simple logic: First version is AI.
    ai_version = db.query(ReportVersion).filter(
        ReportVersion.case_id == case_id,
        ReportVersion.version_number == 1
    ).first()
    
    if ai_version:
        # 3. THE GOLD MINE: Create Training Pair
        pair = MLTrainingPair(
            case_id=case_id,
            ai_version_id=ai_version.id,
            final_version_id=final_version.id
        )
        db.add(pair)
        
    db.commit()
    return final_version

def trigger_extraction_task(doc_id: UUID, org_id: str):
    """
    Enqueues a task to Cloud Tasks to process the document.
    """
    if settings.RUN_LOCALLY:
        logger.info(f"Skipping Cloud Task for doc {doc_id} (Running Locally)")
        return

    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH
        
        # Construct the request body
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/tasks/process-document",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.RESOLVED_BACKEND_URL,
                },
                "body": json.dumps({
                    "document_id": str(doc_id),
                    "organization_id": org_id
                }).encode()
            }
        }
        
        logger.info(f"🚀 Enqueuing extraction task for doc {doc_id} to {parent}")
        
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
        logger.info(f"Skipping Cloud Task for case {case_id} (Running Locally)")
        return

    try:
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.RESOLVED_BACKEND_URL}/tasks/process-case",
                "headers": {"Content-Type": "application/json"},
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SA_EMAIL,
                    "audience": settings.RESOLVED_BACKEND_URL,
                },
                "body": json.dumps({
                    "case_id": str(case_id),
                    "organization_id": org_id
                }).encode()
            }
        }
        
        logger.info(f"🚀 Enqueuing case processing task for case {case_id}")
        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"Task created: {response.name}")
        
    except Exception as e:
        logger.error(f"Failed to enqueue case processing task for case {case_id}: {e}")
        # Re-raise to propagate error to caller (API endpoint returns HTTP error)
        raise

async def process_document_extraction(doc_id: UUID, org_id: str, db: Session):
    """
    Actual logic to process the document (Download -> Extract -> Save).
    """
    """
    Actual logic to process the document (Download -> Extract -> Save).
    """
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return

    tmp_dir = tempfile.mkdtemp()
    try:
        async with extraction_semaphore:
            # 1. Download
            local_filename = f"extract_{doc.id}_{doc.filename}"
            local_path = os.path.join(tmp_dir, local_filename)
            
            logger.info(f"Downloading {doc.gcs_path} for extraction...")
            await asyncio.to_thread(download_file_to_temp, doc.gcs_path, local_path)
            
            # 2. Extract
            logger.info(f"Extracting text from {local_filename}...")
            processed = await asyncio.to_thread(document_processor.process_uploaded_file, local_path, tmp_dir)

            # --- LOGIC FIX START: Persist extracted artifacts to GCS ---
            storage_client = get_storage_client()
            bucket_name = settings.STORAGE_BUCKET_NAME
            bucket = storage_client.bucket(bucket_name)

            for item in processed:
                # If the item has a local path that is NOT the original file we downloaded,
                # it is an artifact (attachment/split page) that must be persisted.
                item_path = item.get("path")
                if item_path and item_path != local_path and os.path.exists(item_path):
                    # Generate a stable GCS path for this artifact
                    # Structure: uploads/{org}/{case}/artifacts/{doc_id}_{filename}
                    artifact_filename = os.path.basename(item_path)
                    blob_name = f"uploads/{doc.organization_id}/{doc.case_id}/artifacts/{doc.id}_{artifact_filename}"
                    
                    logger.info(f"Uploading extracted artifact {artifact_filename} to GCS...")
                    
                    # Upload to GCS
                    blob = bucket.blob(blob_name)
                    await asyncio.to_thread(blob.upload_from_filename, item_path)
                    
                    # SAVE the specific GCS path in the metadata so Generation can find it
                    item["item_gcs_path"] = f"gs://{bucket_name}/{blob_name}"
                else:
                    pass
            # --- LOGIC FIX END ---
            
        # 3. Save to DB
        doc.ai_extracted_data = processed
        doc.ai_status = "processed"
        db.commit()
        logger.info(f"Extraction complete for {doc.id}")
        
    except Exception as e:
        logger.error(f"Error extracting document {doc.id}: {e}")
        doc.ai_status = "error"
        db.commit()
    finally:
        shutil.rmtree(tmp_dir)

    # 4. Check for Case Completion (Fan-in)
    # We do this OUTSIDE the try/except block for the single doc, 
    # but we need to be careful. If this doc failed, should we still check?
    # Yes, because maybe all other docs are done and this one failed.
    
    # Re-query to get fresh state of all docs
    # We need to lock the Case to prevent race conditions where two workers finish at same time
    # and both think they are the last one.
    
    try:
        # Lock the Case immediately
        case = db.query(Case).filter(Case.id == doc.case_id).with_for_update().first()
        
        # Check if we are already generating to fail fast
        if case.status == "generating":
            logger.info(f"Case {doc.case_id} is already generating. Skipping completion check.")
            return

        # Re-query all docs inside this locked transaction
        all_docs = db.query(Document).filter(Document.case_id == doc.case_id).all()
        
        pending_docs = [d for d in all_docs if d.ai_status not in ["processed", "error"]]
        
        if not pending_docs:
            logger.info(f"All documents for case {doc.case_id} finished. Triggering generation.")
            
            # CRITICAL: Set status here to prevent the other worker from entering
            case.status = "generating" 
            db.commit() 
            
            # Trigger Generation Task
            from app.services import report_generation_service
            # We need to run this async. Since we are in an async function, we can await.
            # Wrap in try/except for automatic retry: if this fails, Cloud Tasks will
            # retry this document task, which will re-trigger the completion check.
            try:
                await report_generation_service.trigger_generation_task(str(doc.case_id), str(org_id))
            except Exception as e:
                logger.error(f"Failed to trigger generation for case {doc.case_id}: {e}")
                # CRITICAL: Revert status so retry can happen
                case.status = "processing"
                db.commit()
                # Raise so Cloud Tasks retries this document task
                raise e
            
    except Exception as e:
        # Rollback in case of error during the lock/check
        db.rollback()
        logger.error(f"Error checking case completion: {e}")
        # Re-raise to ensure Cloud Tasks retries
        raise e


# -----------------------------------------------------------------------------
# SYNCHRONOUS WRAPPERS
# -----------------------------------------------------------------------------
import threading
extraction_sync_semaphore = threading.BoundedSemaphore(5)

def process_document_extraction_sync(doc_id: UUID, org_id: str, db: Session):
    """
    Synchronous version of process_document_extraction.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return

    tmp_dir = tempfile.mkdtemp()
    try:
        with extraction_sync_semaphore:
            # 1. Download
            local_filename = f"extract_{doc.id}_{doc.filename}"
            local_path = os.path.join(tmp_dir, local_filename)
            
            logger.info(f"Downloading {doc.gcs_path} for extraction...")
            download_file_to_temp(doc.gcs_path, local_path)
            
            # 2. Extract
            logger.info(f"Extracting text from {local_filename}...")
            processed = document_processor.process_uploaded_file(local_path, tmp_dir)

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
            
        # 3. Save to DB
        doc.ai_extracted_data = processed
        doc.ai_status = "processed"
        db.commit()
        logger.info(f"Extraction complete for {doc.id}")
        
    except Exception as e:
        logger.error(f"Error extracting document {doc.id}: {e}")
        doc.ai_status = "error"
        db.commit()
    finally:
        shutil.rmtree(tmp_dir)

    # 4. Check for Case Completion (Fan-in)
    try:
        case = db.query(Case).filter(Case.id == doc.case_id).with_for_update().first()
        
        if case.status == "generating":
            logger.info(f"Case {doc.case_id} is already generating. Skipping completion check.")
            return

        all_docs = db.query(Document).filter(Document.case_id == doc.case_id).all()
        pending_docs = [d for d in all_docs if d.ai_status not in ["processed", "error"]]
        
        if not pending_docs:
            logger.info(f"All documents for case {doc.case_id} finished. Triggering generation.")
            
            case.status = "generating" 
            db.commit() 
            
            # Trigger Generation Task (SYNC)
            from app.services import report_generation_service
            try:
                report_generation_service.trigger_generation_task_sync(str(doc.case_id), str(org_id))
            except Exception as e:
                logger.error(f"Failed to trigger generation for case {doc.case_id}: {e}")
                case.status = "processing"
                db.commit()
                raise e
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error checking case completion: {e}")
        raise e

