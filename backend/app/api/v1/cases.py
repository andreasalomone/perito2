import logging
import re
from pathlib import Path
from typing import Annotated, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app import schemas
from app.api.dependencies import get_current_user_token, get_db
from app.core.config import settings
from app.models import Case, Client, Document, ReportVersion, User
from app.schemas.enums import CaseStatus, ExtractionStatus
from app.services import case_service, gcs_service
from app.services import report_generation_service as generation_service 

# Configure structured logging
logger = logging.getLogger("app.api.cases")

router = APIRouter()

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/",
    response_model=List[schemas.CaseSummary],
    summary="List Cases",
    description="Retrieve a paginated list of cases for the authenticated organization."
)
def list_cases(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user_token)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    client_id: Optional[UUID] = Query(None),
    status: Optional[CaseStatus] = Query(None),
    scope: str = Query("all", pattern="^(all|mine)$"),
) -> List[Case]:
    """
    Fetches cases with RLS and Soft Delete filtering.
    """
    stmt = (
        select(Case)
        .options(
            selectinload(Case.client),
            # Optimize: Load only creator email
            selectinload(Case.creator).load_only(User.email)
        )
        .order_by(Case.created_at.desc())
    )
    
    # Soft Delete Filter
    stmt = stmt.where(Case.deleted_at.is_(None))

    # 0. Scope Filter ("My Cases")
    if scope == "mine":
        stmt = stmt.where(Case.creator_id == current_user["uid"])

    # 1. Text Search
    if search:
        stmt = stmt.join(Case.client, isouter=True).where(
            (Case.reference_code.ilike(f"%{search}%")) |
            (Client.name.ilike(f"%{search}%"))
        )
    
    # 2. Filter by Client ID
    if client_id:
        stmt = stmt.where(Case.client_id == client_id)
        
    # 3. Filter by Status
    if status:
        stmt = stmt.where(Case.status == status)

    return list(db.scalars(stmt.offset(skip).limit(limit)).all())


@router.get(
    "/{case_id}/status", 
    response_model=schemas.CaseStatusRead,
    summary="Get Case Status"
)
def get_case_status(
    case_id: UUID, 
    db: Annotated[Session, Depends(get_db)]
) -> dict:
    """
    Lightweight polling endpoint. 
    Returns boolean status + granular progress stats.
    """
    # 1. Fetch Case Status
    case = db.scalar(
        select(Case).where(Case.id == case_id, Case.deleted_at.is_(None))
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # 2. Fetch Document Meta
    docs_stmt = (
        select(Document.id, Document.ai_status, Document.created_at, Document.filename)
        .where(Document.case_id == case_id)
    )
    docs = db.execute(docs_stmt).all()
    
    documents_data = [
        {
            "id": row.id, 
            "ai_status": row.ai_status, 
            "created_at": row.created_at,
            "filename": row.filename
        } 
        for row in docs
    ]

    # 3. Calculate Processing State
    is_generating = (case.status == CaseStatus.GENERATING) or any(
        d["ai_status"] in [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING] for d in documents_data
    )
    
    return {
        "id": case_id,
        "status": case.status,
        "documents": documents_data,
        "is_generating": is_generating
    }


@router.post(
    "/", 
    response_model=schemas.CaseDetail, 
    status_code=status.HTTP_201_CREATED,
    summary="Create Case"
)
def create_case(
    case_in: schemas.CaseCreate,
    current_user: Annotated[dict[str, Any], Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)]
) -> Case:
    """
    Creates a new case. Logic delegated to Service layer.
    """
    # Retrieve user to get Organization ID (needed for service)
    # Ideally the service would do this, but we keep the router simple for now
    user = db.get(User, current_user["uid"])
    if not user:
        raise HTTPException(status_code=403, detail="User account not found.")

    return case_service.create_case_with_client(
        db=db,
        case_data=case_in,
        user_uid=current_user["uid"],
        user_org_id=user.organization_id # Pass the Object UUID
    )


@router.get("/{case_id}", response_model=schemas.CaseDetail)
def get_case_detail(
    case_id: UUID, 
    db: Annotated[Session, Depends(get_db)]
) -> Case:
    stmt = (
        select(Case)
        .options(
            selectinload(Case.documents), 
            selectinload(Case.report_versions),
            selectinload(Case.creator).load_only(User.email)
        )
        .where(Case.id == case_id, Case.deleted_at.is_(None))
    )
    case = db.scalar(stmt)
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/documents/upload-url")
def get_doc_upload_url(
    case_id: UUID, 
    filename: str, 
    content_type: str,
    db: Annotated[Session, Depends(get_db)]
) -> dict:
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Sanitize Filename (Strict Regex)
    clean_filename = Path(filename).name
    # Use the regex from case_service or a local constant if not exported? 
    # Just use basic check here or import. 
    if not re.match(r"^[a-zA-Z0-9_\-\. ]+$", clean_filename):
         raise HTTPException(status_code=400, detail="Invalid filename characters.")

    # 2. Validate Extension & MIME
    ext = Path(clean_filename).suffix.lower()
    if ext not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")
    
    if content_type != settings.ALLOWED_MIME_TYPES[ext]:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type mismatch. Expected {settings.ALLOWED_MIME_TYPES[ext]}."
        )

    # 3. Generate URL
    return gcs_service.generate_upload_signed_url(
        filename=clean_filename,
        content_type=content_type,
        organization_id=str(case.organization_id),
        case_id=str(case.id)
    )


@router.post(
    "/{case_id}/documents/register", 
    response_model=schemas.DocumentRead
)
def register_document(
    case_id: UUID,
    payload: schemas.DocumentRegisterPayload,
    db: Annotated[Session, Depends(get_db)]
) -> Document:
    """
    Registers a GCS blob as a Document.
    Uses centralized path validation from Service layer.
    """
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Security: Path Validation (Prevent IDOR)
    clean_path = case_service.validate_storage_path(
        raw_path=payload.gcs_path,
        org_id=case.organization_id,
        case_id=case.id,
        allowed_prefixes=["uploads"]
    )

    # 2. Create Record
    new_doc = Document(
        case_id=case.id,
        organization_id=case.organization_id,
        filename=payload.filename,
        gcs_path=clean_path,
        mime_type=payload.mime_type,
        ai_status=ExtractionStatus.PENDING
    )
    db.add(new_doc)
    
    # 2.5. Tag blob as finalized BEFORE commit
    # If this fails, we fail the request. The file remains an orphan (db undefined),
    # and will be cleaned up by the daily job.
    try:
        gcs_service.tag_blob_as_finalized(clean_path)
    except Exception as e:
        logger.error(f"Failed to tag blob {clean_path} as finalized: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, 
            detail="Failed to finalize document storage."
        )

    # 3. Commit only if tagging succeeded (or we are okay with it, but here we enforce it)
    db.commit()
    
    # RE-APPLY RLS CONTEXT (Fix for QueuePool connection swap after commit)
    # db.commit() may release connection to pool, and db.refresh() gets a new one
    # without the RLS session variables set.
    from sqlalchemy import text
    try:
        db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"), 
            {"oid": str(case.organization_id)}
        )
    except Exception as e:
        logger.warning(f"Failed to re-apply RLS context before refresh: {e}")
    
    db.refresh(new_doc)
    
    # 3. Trigger Async Processing
    case_service.trigger_extraction_task(new_doc.id, str(case.organization_id))
    
    return new_doc


@router.post("/{case_id}/generate")
async def trigger_generation(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)]
) -> dict:
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    if settings.RUN_LOCALLY:
        # LOCAL DEV
        background_tasks.add_task(
            generation_service.process_case_logic,
            case_id=str(case.id),
            organization_id=str(case.organization_id)
        )
    else:
        # PROD: Cloud Tasks
        case_service.trigger_case_processing_task(str(case.id), str(case.organization_id))
    
    return {"status": "generation_started"}


@router.post("/{case_id}/finalize", response_model=schemas.VersionRead)
def finalize_case_endpoint(
    case_id: UUID,
    payload: schemas.FinalizePayload,
    db: Annotated[Session, Depends(get_db)]
) -> ReportVersion:
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Validated Path
    clean_path = case_service.validate_storage_path(
        raw_path=payload.final_docx_path,
        org_id=case.organization_id,
        case_id=case.id,
        allowed_prefixes=["uploads", "reports"]
    )

    # 2. Execute Service
    final_version = case_service.finalize_case(
        db=db,
        case_id=case.id,
        org_id=case.organization_id,
        final_docx_path=clean_path
    )
    
    return final_version


@router.post("/{case_id}/versions/{version_id}/download")
async def download_version(
    case_id: UUID,
    version_id: UUID,
    payload: schemas.DownloadVariantPayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user_token)]
) -> dict:
    # Validate Case
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # Validate Version
    stmt = select(ReportVersion).where(
        ReportVersion.id == version_id, 
        ReportVersion.case_id == case_id
    )
    version = db.scalar(stmt)
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        if version.is_final:
            if not version.docx_storage_path:
                 raise HTTPException(status_code=404, detail="File path missing.")
            
            url = gcs_service.generate_download_signed_url(version.docx_storage_path)
            return {"download_url": url}
        else:
            # Generate variant logic
            url = await generation_service.generate_docx_variant(
                version_id=str(version_id),
                template_type=payload.template_type,
                db=db
            )
            return {"download_url": url}
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Download generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Soft-deletes a case.
    """
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # Check permissions? 
    # Current RLS allows owner/org member. 
    # Maybe only creator should delete? 
    # For now, org level access is assumed fine.
    
    from datetime import datetime
    case.deleted_at = datetime.utcnow()
    db.commit()
    logger.info(f"Case {case_id} soft-deleted.")
    return
