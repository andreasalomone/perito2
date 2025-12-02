from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List

from app.db.database import get_db
from app.models import Case
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class TaskPayload(BaseModel):
    case_id: str
    organization_id: str

class DocumentTaskPayload(BaseModel):
    document_id: str
    organization_id: str


async def verify_cloud_tasks_auth(
    request: Request,
    authorization: str = Header(None)
):
    """
    Validates that the request comes from a legitimate Cloud Task
    by verifying the OIDC token in the Authorization header.
    """
    if settings.RUN_LOCALLY:
        return True

    if not authorization:
        logger.warning("⛔ Blocked task: Missing Authorization header")
        raise HTTPException(status_code=403, detail="Missing Authorization header")

    try:
        # Bearer <token>
        token = authorization.split(" ")[1]
        
        # Verify the token against Google's public certs
        # audience should match your Backend URL or the specific service account logic
        # For Cloud Run, audience is usually the Service URL.
        # Ensure settings.BACKEND_URL is the OIDC audience.
        id_info = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            audience=settings.BACKEND_URL 
        )
        
        # Optional: Check issuer
        if id_info['iss'] != 'https://accounts.google.com':
             raise ValueError('Wrong issuer.')
             
        return True

    except Exception as e:
        logger.error(f"⛔ Task Auth Failed: {e}")
        raise HTTPException(status_code=403, detail="Invalid OIDC Token")

@router.post("/process-case")
async def process_case(
    payload: TaskPayload, 
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_cloud_tasks_auth)
):
    logger.info(f"🚀 Starting task for case {payload.case_id} in org {payload.organization_id}")

    # 1. Manually set RLS context for the worker (Securely)
    # Use set_config to avoid SQL injection
    db.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"), 
        {"org_id": payload.organization_id}
    )
    
    # 2. Now the worker can see the case
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        logger.error("❌ Worker cannot find case (RLS Blocked or Invalid ID)")
        raise HTTPException(status_code=404, detail="Case not found")
        
    # 3. Run Logic...
    # We await the synchronous logic (or run it directly if it's async)
    from app.services import report_generation_service as generation_service
    
    # Run the generation logic
    # Note: process_case_logic is async, so we await it
    await generation_service.process_case_logic(
        case_id=payload.case_id,
        organization_id=payload.organization_id,
        db=db
    )
    
    logger.info(f"✅ Case {case.reference_code} processed successfully.")
    
    return {"status": "success"}

@router.post("/process-document")
async def process_document(
    payload: DocumentTaskPayload,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_cloud_tasks_auth)
):
    logger.info(f"🚀 Starting extraction task for doc {payload.document_id} in org {payload.organization_id}")

    # 1. Set RLS (Securely)
    db.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"), 
        {"org_id": payload.organization_id}
    )

    # 2. Get Document
    from app.models import Document
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        logger.error("❌ Worker cannot find document")
        raise HTTPException(status_code=404, detail="Document not found")

    # 3. Run Extraction Logic
    # We need to import the logic. Since it involves downloading and processing, 
    # we might want to put this logic in a service method to keep the route clean.
    # But for now, let's keep it here or call a new method in case_service.
    
    from app.services import case_service
    await case_service.process_document_extraction(doc.id, payload.organization_id, db)

    logger.info(f"✅ Document {doc.filename} processed successfully.")
    return {"status": "success"}