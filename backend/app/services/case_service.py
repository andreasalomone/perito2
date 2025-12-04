from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from app.models import Case, ReportVersion, MLTrainingPair, Document, Client
from app.schemas.enums import ExtractionStatus, CaseStatus
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
    
    # 2. Find the original AI Draft
    # FIX: Don't hardcode version_number == 1, as it may be missing if regenerated or pre-draft exists
    # Instead, find the earliest non-final version
    ai_version = db.query(ReportVersion).filter(
        ReportVersion.case_id == case_id,
        ReportVersion.is_final == False
    ).order_by(ReportVersion.version_number.asc()).first()
    
    if ai_version:
        # 3. THE GOLD MINE: Create Training Pair
        pair = MLTrainingPair(
            case_id=case_id,
            ai_version_id=ai_version.id,
            final_version_id=final_version.id
        )
        db.add(pair)
    else:
        logger.warning(f"No AI draft version found for case {case_id}. ML training pair not created.")
        
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
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return
    
    # FIX: Idempotency Check - Skip extraction if already processed
    # This prevents expensive re-downloads and re-extractions on Cloud Tasks retries
    if doc.ai_status == ExtractionStatus.SUCCESS:
        logger.info(f"Document {doc.id} already processed. Skipping extraction, proceeding to Fan-In check.")
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
            db.commit()
            logger.info(f"Extraction complete for {doc.id}")
            
        except Exception as e:
            logger.error(f"Error extracting document {doc.id}: {e}")
            doc.ai_status = ExtractionStatus.ERROR
            db.commit()
        finally:
            shutil.rmtree(tmp_dir)

    # 4. Check for Case Completion (Fan-in)
    await _check_and_trigger_generation(db, doc.case_id, org_id, is_async=True)





def _perform_extraction_logic(doc: Document, tmp_dir: str):
    """
    Core extraction logic: Download -> Extract -> Upload Artifacts.
    This function is SYNCHRONOUS and blocking.
    """
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
    
    # Update doc object (in memory, caller saves to DB)
    doc.ai_extracted_data = processed


async def _check_and_trigger_generation(db: Session, case_id: UUID, org_id: str, is_async: bool = True):
    """
    Checks if all documents are processed and triggers generation if so.
    """
    try:
        # Lock the Case immediately
        case = db.query(Case).filter(Case.id == case_id).with_for_update().first()
        
        # Check if we are already generating to fail fast
        if case.status == CaseStatus.GENERATING:
            logger.info(f"Case {case_id} is already generating. Skipping completion check.")
            return

        # Re-query all docs inside this locked transaction
        all_docs = db.query(Document).filter(Document.case_id == case_id).all()
        
        # Check if all documents are processed (SUCCESS, ERROR, or SKIPPED)
        pending_docs = [d for d in all_docs if d.ai_status not in [ExtractionStatus.SUCCESS, ExtractionStatus.ERROR, ExtractionStatus.SKIPPED]]
        
        if not pending_docs:
            logger.info(f"All documents for case {case_id} finished. Triggering generation.")
            
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
                    payload={
                        "case_id": str(case_id),
                        "organization_id": str(org_id)
                    }
                )
                db.add(outbox_entry)
                
                # 3. Atomic Commit
                # If this fails, BOTH the status update and the message insert are rolled back.
                # No Zombie state is possible.
                db.commit()
                
                # 4. Attempt Immediate Dispatch (Best Effort / Optimization)
                # We try to send it now for speed. If this fails, the background poller will catch it.
                if is_async:
                    try:
                        from app.services.outbox_processor import process_message
                        await process_message(outbox_entry.id, db)
                    except Exception as e:
                        logger.warning(f"Immediate dispatch failed (will retry via cron): {e}")
                        # Do NOT re-raise. The data is safe in the DB.
                else:
                    # For sync path, we skip immediate dispatch and rely on the poller
                    # because process_message is async.
                    logger.info("Skipping immediate dispatch in sync mode (will be picked up by poller)")

            except Exception as e:
                db.rollback()
                logger.error(f"Error checking case completion: {e}")
                raise e
            
    except Exception as e:
        # Rollback in case of error during the lock/check
        db.rollback()
        logger.error(f"Error checking case completion: {e}")
        # Re-raise to ensure Cloud Tasks retries
        raise e



