from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from app.models import Case, ReportVersion, MLTrainingPair, Document, Client
from app.core.config import settings
import logging
import json
from google.cloud import tasks_v2

logger = logging.getLogger(__name__)


from sqlalchemy.exc import IntegrityError

def get_or_create_client(db: Session, name: str) -> Client:
    # 1. Try to find existing
    client = db.query(Client).filter(Client.name == name).first()
    if client:
        return client

    # 2. Try to create (Handle Race Condition)
    # 2. Try to create (Handle Race Condition)
    # Fetch current org_id from session variable first
    result = db.execute(text("SELECT current_setting('app.current_org_id', true)")).scalar()
    
    if not result:
        logger.error("Attempted to create client without app.current_org_id set.")
        raise ValueError("Missing Organization Context")

    try:
        client = Client(name=name, organization_id=result)
        db.add(client)
        db.commit()
        db.refresh(client)
        return client
        
    except IntegrityError:
        # Race condition: Someone else created it just now.
        db.rollback()
        return db.query(Client).filter(Client.name == name, Client.organization_id == result).one()

# --- THE CRITICAL WORKFLOWS ---

def create_ai_version(db: Session, case_id: UUID, org_id: UUID, ai_text: str, docx_path: str):
    """
    Called by the Worker after Gemini finishes.
    Creates Version 1 (or next version).
    """
    # 0. LOCK the Case to prevent version race conditions
    # This ensures only one transaction can add a version at a time for this case.
    db.query(Case).filter(Case.id == case_id).with_for_update().first()

    # 1. Determine version number
    count = db.query(ReportVersion).filter(ReportVersion.case_id == case_id).count()
    next_version = count + 1
    
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
    db.commit()
    return version

def finalize_case(db: Session, case_id: UUID, org_id: UUID, final_docx_path: str):
    """
    Called when User uploads the final "signed" PDF/DOCX.
    1. Save new version.
    2. Mark as Final.
    3. Create ML Training Pair.
    """
    # 1. Create Final Version
    count = db.query(ReportVersion).filter(ReportVersion.case_id == case_id).count()
    final_version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=count + 1,
        docx_storage_path=final_docx_path,
        is_final=True
    )
    db.add(final_version)
    db.flush() # Get ID
    
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
                "url": f"{settings.BACKEND_URL}/tasks/process-document",
                "headers": {"Content-Type": "application/json"},
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
        logger.error(f"Failed to enqueue task: {e}")

async def process_document_extraction(doc_id: UUID, org_id: str, db: Session):
    """
    Actual logic to process the document (Download -> Extract -> Save).
    """
    import os
    import tempfile
    import shutil
    import asyncio
    from app.services import document_processor
    from app.services.gcs_service import download_file_to_temp
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return

    tmp_dir = tempfile.mkdtemp()
    try:
        # 1. Download
        local_filename = f"extract_{doc.id}_{doc.filename}"
        local_path = os.path.join(tmp_dir, local_filename)
        
        logger.info(f"Downloading {doc.gcs_path} for extraction...")
        await asyncio.to_thread(download_file_to_temp, doc.gcs_path, local_path)
        
        # 2. Extract
        logger.info(f"Extracting text from {local_filename}...")
        processed = await asyncio.to_thread(document_processor.process_uploaded_file, local_path, tmp_dir)
        
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

