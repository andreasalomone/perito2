from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List

from database import get_db
from core.models import Case
from config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class TaskPayload(BaseModel):
    case_id: str
    organization_id: str

async def verify_cloud_tasks_auth(
    x_cloudtasks_queuename: str = Header(None, alias="X-AppEngine-QueueName"),
    oidc_token: str = Header(None, alias="Authorization")
):
    """
    Security Guard: Ensures the request is from Google Cloud Tasks.
    """
    # 1. Bypass check if running locally (for development speed)
    if settings.RUN_LOCALLY:
        return True
        
    # 2. Google strips this header from external requests. 
    # If it is present, the request is trusted (internal Google traffic).
    if not x_cloudtasks_queuename:
        logger.warning("⛔ Security Alert: Blocked unauthorized access to /tasks/ endpoint.")
        raise HTTPException(status_code=403, detail="Access denied: Not a Cloud Task")
    
    return True

@router.post("/process-case")
async def process_case(
    payload: TaskPayload, 
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_cloud_tasks_auth)
):
    logger.info(f"🚀 Starting task for case {payload.case_id} in org {payload.organization_id}")

    # 1. Manually set RLS context for the worker
    # The worker is a "superuser" in terms of connection, but needs to assume the tenant identity
    db.execute(text(f"SET app.current_org_id = '{payload.organization_id}'"))
    
    # 2. Now the worker can see the case
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        logger.error("❌ Worker cannot find case (RLS Blocked or Invalid ID)")
        raise HTTPException(status_code=404, detail="Case not found")
        
    # 3. Run Logic...
    # We await the synchronous logic (or run it directly if it's async)
    from services import generation_service
    
    # Run the generation logic
    # Note: process_case_logic is async, so we await it
    await generation_service.process_case_logic(
        case_id=payload.case_id,
        organization_id=payload.organization_id,
        db=db
    )
    
    logger.info(f"✅ Case {case.reference_code} processed successfully.")
    
    return {"status": "success"}