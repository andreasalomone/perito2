import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel, UUID4, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models import Case, Document
from app.services import report_generation_service, case_service

# Configure Structured Logging
logger = logging.getLogger("app.tasks")

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. Strict Pydantic Models
# -----------------------------------------------------------------------------
class TaskBase(BaseModel):
    organization_id: UUID4 = Field(..., description="Target Organization UUID")

class CaseTaskPayload(TaskBase):
    case_id: UUID4 = Field(..., description="Target Case UUID")

class DocumentTaskPayload(TaskBase):
    document_id: UUID4 = Field(..., description="Target Document UUID")

# -----------------------------------------------------------------------------
# 2. Security & Auth Dependencies
# -----------------------------------------------------------------------------
def verify_cloud_tasks_auth(
    authorization: Annotated[str | None, Header()] = None
) -> Literal[True]:
    """
    Validates that the request originates from a trusted Google Cloud Task.
    Verifies the OIDC ID Token signed by Google.
    """
    # Fail-safe: Strict check for production environment
    if settings.ENVIRONMENT == "local" and settings.RUN_LOCALLY:
        logger.debug("⚠️ Skipping Cloud Task Auth (Local Mode)")
        return True

    if not authorization:
        logger.warning("⛔ Auth Failed: Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing Authorization header"
        )

    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
             raise ValueError("Invalid header format")

        # Verify OIDC Token
        # Audience must match the Service URL exactly
        id_info = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            audience=settings.BACKEND_URL 
        )

    except ValueError as e:
        logger.warning(f"⛔ Token Validation Failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Authentication Token")
    except Exception as e:
        logger.error(f"⛔ Unexpected Auth Error: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authentication Failed")

    # Service Account Whitelist Check
    # Prevents other GCP services in your project from invoking these webhooks
    expected_sa = settings.CLOUD_TASKS_SA_EMAIL
    if expected_sa and id_info.get("email") != expected_sa:
        logger.critical(
            f"⛔ Security Alert: Unauthorized Service Account detected. "
            f"Expected: {expected_sa}, Got: {id_info.get('email')}"
        )
        raise HTTPException(status_code=403, detail="Forbidden: Service Account Mismatch")

    return True

# -----------------------------------------------------------------------------
# 3. RLS Context Manager
# -----------------------------------------------------------------------------
def set_rls_context(db: Session, organization_id: str) -> None:
    """
    Sets the PostgreSQL session variable for Row-Level Security.
    """
    try:
        db.execute(
            text("SELECT set_config('app.current_org_id', :org_id, false)"),
            {"org_id": str(organization_id)}
        )
    except Exception as e:
        logger.critical(f"❌ Failed to set RLS context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Security Context Failure"
        )

# -----------------------------------------------------------------------------
# 4. Endpoints
# -----------------------------------------------------------------------------

# NOTE: We use 'def' (Synchronous) here because we are using a synchronous
# DB driver (pg8000). FastAPI runs 'def' endpoints in a threadpool.
# Using 'async def' would block the main event loop.

@router.post(
    "/process-case", 
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Case Logic"
)
def process_case(
    payload: CaseTaskPayload,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_cloud_tasks_auth)
):
    """
    Worker endpoint to process case logic (e.g., status updates, initial checks).
    """
    logger.info(f"🚀 Processing Case: {payload.case_id}")
    
    # 1. Apply Security Context
    set_rls_context(db, str(payload.organization_id))
    
    # 2. Validation
    case = db.get(Case, payload.case_id)
    if not case:
        logger.error(f"❌ Case not found: {payload.case_id}")
        # Return 200 to stop Cloud Tasks from retrying infinitely on 404s
        return {"status": "skipped", "reason": "not_found"}

    # 3. Execute Business Logic
    try:
        report_generation_service.process_case_logic_sync(
            case_id=str(payload.case_id),
            organization_id=str(payload.organization_id),
            db=db
        )
    except Exception as e:
        logger.error(f"❌ Task Failure: {e}", exc_info=True)
        # Return 500 to trigger Cloud Tasks retry policy (exponential backoff)
        raise HTTPException(status_code=500, detail="Processing failed")

    return {"status": "success"}


@router.post(
    "/process-document", 
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Document Extraction"
)
def process_document(
    payload: DocumentTaskPayload,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_cloud_tasks_auth)
):
    """
    Worker endpoint to run Gemini AI extraction on a document.
    """
    logger.info(f"🚀 Processing Document: {payload.document_id}")
    
    set_rls_context(db, str(payload.organization_id))

    doc = db.get(Document, payload.document_id)
    if not doc:
        logger.error(f"❌ Document not found: {payload.document_id}")
        return {"status": "skipped", "reason": "not_found"}

    try:
        case_service.process_document_extraction_sync(
            document_id=str(doc.id), 
            organization_id=str(payload.organization_id), 
            db=db
        )
    except Exception as e:
        logger.error(f"❌ Extraction Task Failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Extraction failed")

    return {"status": "success"}


@router.post(
    "/generate-report", 
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate DOCX Report"
)
def generate_report(
    payload: CaseTaskPayload,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_cloud_tasks_auth)
):
    """
    Worker endpoint to compile the final DOCX report.
    """
    logger.info(f"🚀 Generating Report for Case: {payload.case_id}")
    
    set_rls_context(db, str(payload.organization_id))

    try:
        report_generation_service.generate_report_logic_sync(
            case_id=str(payload.case_id),
            organization_id=str(payload.organization_id),
            db=db
        )
    except Exception as e:
        logger.error(f"❌ Report Generation Failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Generation failed")

    return {"status": "success"}


@router.post("/flush-outbox")
async def flush_outbox_endpoint(db: Session = Depends(get_db)):
    """
    Trigger processing of pending outbox messages.
    Called by Cloud Scheduler every minute.
    """
    from app.services.outbox_processor import process_outbox_batch
    await process_outbox_batch(db)
    return {"status": "ok"}