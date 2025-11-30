import json
import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google.cloud import tasks_v2

from database import get_db
from config import settings
from deps import get_current_user
from services.gcs_service import generate_upload_signed_url, generate_download_signed_url
from core.models import ReportLog, ReportStatus, DocumentLog, ExtractionStatus 

import logging
logger = logging.getLogger(__name__) 
# Note: Ensure you moved your models.py to backend/core/models.py

router = APIRouter()

# --- Pydantic Models for Validation ---
from pydantic import BaseModel

class UploadRequest(BaseModel):
    filename: str
    content_type: str

class GenerateRequest(BaseModel):
    # List of GCS paths returned by the upload step
    file_paths: List[str] 
    original_filenames: List[str]

# --- Endpoints ---

@router.post("/upload-url")
def get_upload_url(
    req: UploadRequest, 
    current_user: dict = Depends(get_current_user)
):
    """
    Step 1: Frontend requests a secure URL to upload a file.
    """
    organization_id = current_user.get('organization_id')
    if not organization_id:
        raise HTTPException(status_code=400, detail="User not assigned to an organization")
    
    # Generate unique filename to avoid overwrites
    safe_filename = f"{uuid.uuid4()}_{req.filename}"
    
    data = generate_upload_signed_url(safe_filename, req.content_type, organization_id)
    return data

import os
from services.report_service import generate_report_logic

@router.post("/generate")
async def trigger_generation(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Step 2: Frontend confirms files are uploaded and starts processing.
    """
    user_id = current_user['uid']
    organization_id = current_user.get('organization_id')
    
    if not organization_id:
        raise HTTPException(status_code=400, detail="User not assigned to an organization. Please refresh.")

    report_id = str(uuid.uuid4())

    # 1. Create ReportLog entry (Status: PROCESSING)
    new_report = ReportLog(
        id=report_id,
        user_id=user_id,
        organization_id=organization_id,
        status=ReportStatus.PROCESSING,
        created_at=datetime.utcnow(),
        current_step="queued"
    )
    db.add(new_report)
    
    # 2. Log the documents
    for idx, path in enumerate(req.file_paths):
        # We need to extract the filename from the path if original not provided correctly
        # But req.original_filenames should handle it.
        fname = req.original_filenames[idx] if idx < len(req.original_filenames) else "unknown"
        
        doc_log = DocumentLog(
            id=str(uuid.uuid4()),
            report_id=report_id,
            original_filename=fname,
            stored_filepath=path,
            file_size_bytes=0,
            extraction_status=ExtractionStatus.PROCESSING 
        )
        db.add(doc_log)
    
    db.commit()

    # 3. Dispatch Logic
    if settings.RUN_LOCALLY:
        # --- LOCAL DEV PATH (Synchronous) ---
        logger.warning(f"⚠️ Running task locally for report {report_id}")
        # Run the logic immediately in the background (using FastAPI background tasks would be better, 
        # but awaiting here is fine for testing)
        try:
            await generate_report_logic(report_id, user_id, req.file_paths, db)
        except Exception as e:
            logger.error(f"Error during local execution: {e}")
            # We don't raise HTTP exception here because we already returned 200 technically, 
            # but since we are awaiting, the frontend will see the error.
            raise HTTPException(status_code=500, detail=str(e))
            
    else:
        # --- PRODUCTION PATH (Cloud Tasks) ---
        client = tasks_v2.CloudTasksClient()
        parent = settings.CLOUD_TASKS_QUEUE_PATH
        
        # This URL must be your PUBLIC Cloud Run URL
        # We will configure this env var when deploying
        service_url = os.environ.get("SERVICE_URL", "https://YOUR-CLOUD-RUN-URL.run.app")
        worker_url = f"{service_url}/tasks/process-report"

        task_payload = {
            "report_id": report_id,
            "user_id": user_id,
            "file_paths": req.file_paths
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": worker_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(task_payload).encode()
            }
        }
        
        # Add OIDC Token for security (Cloud Run requires this)
        # It tells Google "I am authorized to call this private service"
        service_account_email = "robotperizia-sa@perito-479708.iam.gserviceaccount.com"
        task["http_request"]["oidc_token"] = {"service_account_email": service_account_email}

        client.create_task(request={"parent": parent, "task": task})

    return {"report_id": report_id, "status": "processing"}

@router.get("/{report_id}/status")
def check_status(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Step 3: Frontend polls this endpoint to update the progress bar.
    """
    report = db.query(ReportLog).filter(ReportLog.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Security: Ensure user owns this report
    # Security: Ensure user belongs to the same organization
    # We allow any member of the org to see the report
    user_org_id = current_user.get('organization_id')
    
    if not user_org_id or report.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    return {
        "status": report.status,
        "progress_logs": report.progress_logs,
        "current_step": report.current_step,
        "error": report.error_message
    }

@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Step 4: Frontend requests the final DOCX.
    We return a secure, temporary link to Google Cloud Storage.
    """
    report = db.query(ReportLog).filter(ReportLog.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Security Check
    # Security Check
    user_org_id = current_user.get('organization_id')
    
    if not user_org_id or report.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if report.status != ReportStatus.SUCCESS or not report.final_docx_path:
        raise HTTPException(status_code=400, detail="Report not ready yet")
        
    # Generate the link
    download_url = generate_download_signed_url(report.final_docx_path)
    
    return {"download_url": download_url}

class ReportSummary(BaseModel):
    id: str
    status: str
    created_at: datetime
    final_docx_path: str | None = None
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[ReportSummary])
def list_reports(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Step 5: List all reports for the user's organization.
    """
    user_org_id = current_user.get('organization_id')
    
    if not user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    reports = db.query(ReportLog).filter(ReportLog.organization_id == user_org_id).order_by(ReportLog.created_at.desc()).all()
    
    return reports