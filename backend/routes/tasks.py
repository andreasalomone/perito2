from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from database import get_db
from services.report_service import generate_report_logic

router = APIRouter()

class TaskPayload(BaseModel):
    report_id: str
    user_id: str
    file_paths: List[str]

@router.post("/process-report")
async def process_report_task(
    payload: TaskPayload,
    db: Session = Depends(get_db)
):
    """
    Cloud Tasks calls this endpoint to start generation.
    It runs the heavy logic (OCR -> LLM -> DOCX).
    """
    print(f"🚀 Starting task for report {payload.report_id}")
    
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
        print(f"❌ Task Failed: {e}")
        # Returning 500 tells Cloud Tasks to retry automatically
        raise HTTPException(status_code=500, detail=str(e))