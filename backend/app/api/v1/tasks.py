import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import UUID4, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_raw_db as get_db
from app.services import case_service, report_generation_service

# Import output processor locally or at top level
from app.services.outbox_processor import process_outbox_batch

# Configure Structured Logging
logger = logging.getLogger("app.tasks")

router = APIRouter()


# -----------------------------------------------------------------------------
# 1. Models
# -----------------------------------------------------------------------------
class TaskBase(BaseModel):
    organization_id: UUID4 = Field(..., description="Target Organization UUID")


class CaseTaskPayload(TaskBase):
    case_id: UUID4 = Field(..., description="Target Case UUID")
    # SECURITY: Strict allowlist for language values
    language: Literal["italian", "english", "spanish"] = Field(
        default="italian", description="Output language for report"
    )
    # Optional extra instructions from expert (max 2000 chars)
    extra_instructions: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Additional LLM instructions from expert",
    )


class DocumentTaskPayload(TaskBase):
    document_id: UUID4 = Field(..., description="Target Document UUID")


# -----------------------------------------------------------------------------
# 2. Dependencies
# -----------------------------------------------------------------------------
# GLOBAL CACHE for Google's public keys
# This object handles caching internally.
_cached_request = google_requests.Request()


def verify_cloud_tasks_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> Literal[True]:
    """
    Validates Google Cloud Task OIDC Token.

    NOTE: This is a synchronous function (def). When used as a dependency
    in an 'async def' route, FastAPI runs it in a threadpool to prevent blocking.
    """
    if settings.ENVIRONMENT == "local" and settings.RUN_LOCALLY:
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ValueError("Invalid header format")

        # Blocking I/O: Makes a request to Google's Certs endpoint
        # Uses the global _cached_request to persist keys
        #
        # NOTE: Cloud Tasks uses the target URL as OIDC audience. We've configured
        # Cloud Run to accept our custom domain (api.perito.my) as a valid audience
        # via --add-custom-audiences. We skip audience verification here since
        # Cloud Run validates it at the edge before the request reaches our code.
        id_info = id_token.verify_oauth2_token(
            token,
            _cached_request,
            audience=None,  # Let Cloud Run handle audience validation
        )

    except Exception as e:
        logger.warning(f"Auth Failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Token") from None

    expected_sa = settings.CLOUD_TASKS_SA_EMAIL
    if id_info.get("email") != expected_sa:
        logger.critical(
            f"Auth Mismatch. Expected: {expected_sa}, Got: {id_info.get('email')}"
        )
        raise HTTPException(status_code=403, detail="Service Account Mismatch")

    return True


# -----------------------------------------------------------------------------
# 3. Async Endpoints (AI & I/O Bound)
# -----------------------------------------------------------------------------
# These endpoints do NOT touch the sync DB Session directly.
# They delegate to async services which manage their own sessions if needed.


@router.post(
    "/process-case", status_code=status.HTTP_202_ACCEPTED, summary="Process Case Logic"
)
async def process_case(
    payload: CaseTaskPayload, _: bool = Depends(verify_cloud_tasks_auth)
):
    """
    Async Worker: Handles business logic updates.
    """
    logger.info(f"🚀 Processing Case: {payload.case_id}")
    try:
        # Natively await the service. No asyncio.run() overhead.
        await report_generation_service.run_process_case_logic_standalone(
            case_id=str(payload.case_id), organization_id=str(payload.organization_id)
        )
    except Exception as e:
        logger.error(f"❌ Case Task Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Processing failed") from e
    return {"status": "success"}


@router.post(
    "/process-document",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Document Extraction",
)
async def process_document(
    payload: DocumentTaskPayload, _: bool = Depends(verify_cloud_tasks_auth)
):
    """
    Async Worker: Handles heavy AI extraction.
    """
    logger.info(f"🚀 Processing Document: {payload.document_id}")
    try:
        await case_service.run_process_document_extraction_standalone(
            doc_id=payload.document_id, org_id=str(payload.organization_id)
        )
    except Exception as e:
        logger.error(f"❌ Doc Task Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Extraction failed") from e
    return {"status": "success"}


@router.post("/generate-report", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    payload: CaseTaskPayload, _: bool = Depends(verify_cloud_tasks_auth)
):
    """
    Async Worker: Compiles DOCX.
    """
    logger.info(
        f"🚀 Generating Report: {payload.case_id} (language: {payload.language})"
    )
    try:
        await report_generation_service.run_generation_task(
            case_id=str(payload.case_id),
            organization_id=str(payload.organization_id),
            language=payload.language,
            extra_instructions=payload.extra_instructions,
        )
    except Exception as e:
        logger.error(f"❌ Gen Task Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Generation failed") from e
    return {"status": "success"}


class EnrichClientPayload(BaseModel):
    """Payload for ICE client enrichment task."""

    client_id: str = Field(..., description="Client UUID to enrich")
    original_name: str = Field(..., description="Original client name for search query")
    organization_id: str = Field(..., description="Organization UUID for RLS context")


@router.post(
    "/enrich-client",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enrich Client with AI (ICE)",
)
async def enrich_client(
    payload: EnrichClientPayload,
    db: Annotated[Session, Depends(get_db)],
    _: bool = Depends(verify_cloud_tasks_auth),
):
    """
    ICE (Intelligent Client Enrichment) Worker.

    Fetches corporate details from Gemini with Google Search grounding:
    - Full legal name (Ragione Sociale)
    - VAT number (Partita IVA)
    - Registered address (Sede Legale)
    - Official website
    - Company logo (via Google Favicon API)
    """
    from sqlalchemy import text

    logger.info(
        f"🧠 ICE: Enriching client {payload.client_id} ('{payload.original_name}')"
    )

    # SECURITY FIX: Set RLS context BEFORE any ORM queries
    # This is required because Cloud Tasks don't have user tokens
    db.execute(
        text("SELECT set_config('app.current_org_id', :oid, false)"),
        {"oid": payload.organization_id},
    )

    try:
        from app.services.enrichment_service import EnrichmentService

        service = EnrichmentService()
        success = await service.enrich_and_update_client(
            client_id=payload.client_id,
            original_name=payload.original_name,
            db=db,
        )

        if success:
            logger.info(f"✅ ICE: Client {payload.client_id} enriched successfully")
        else:
            logger.warning(
                f"⚠️ ICE: Client {payload.client_id} enrichment failed or no data found"
            )

    except Exception as e:
        logger.error(f"❌ ICE Task Failed for {payload.client_id}: {e}", exc_info=True)
        # Don't raise - enrichment failure shouldn't cause Cloud Tasks retry

    return {"status": "success"}


# -----------------------------------------------------------------------------
# 4. Sync Endpoints (DB Bound)
# -----------------------------------------------------------------------------
# This endpoint uses 'db: Session', which is a synchronous dependency.
# Therefore, this route MUST be 'def' (Sync).


@router.post("/flush-outbox")
def flush_outbox_endpoint(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_cloud_tasks_auth),  # Require Cloud Tasks OIDC auth
):
    """
    Sync Worker: Flushes DB Outbox.
    Must be synchronous because it relies on the global Sync DB session pattern.
    """
    # Verify auth manually or add dependency here if needed
    # (Usually called by Scheduler via App Engine internal logic)
    process_outbox_batch(db)
    return {"status": "ok"}
