from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from database import get_db
from services.report_service import generate_report_logic

from config import settings

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class TaskPayload(BaseModel):
    report_id: str
    user_id: str
    file_paths: List[str]

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

@router.post("/process-report")
async def process_report_task(
    payload: TaskPayload,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_cloud_tasks_auth) # <--- The Guard
):
    """
    Cloud Tasks calls this endpoint to start generation.
    It runs the heavy logic (OCR -> LLM -> DOCX).
    """
    logger.info(f"🚀 Starting task for report {payload.report_id}")
    
    try:
        # We await the synchronous logic (or run it directly)
        # This function contains your core business logic
        await generate_report_logic(
            report_id=payload.report_id, 
            user_id=payload.user_id,
            file_paths=payload.file_paths,
            db=db
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ Task Failed: {e}", exc_info=True)
        # Returning 500 tells Cloud Tasks to retry automatically
        raise HTTPException(status_code=500, detail=str(e))