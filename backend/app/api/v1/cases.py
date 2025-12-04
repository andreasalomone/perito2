import logging
import re
from pathlib import Path
from typing import Annotated, List, Optional
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
# In a real scenario, we assume report_generation_service is refactored 
# to create its own DB session, not accept one as an arg.
from app.services import report_generation_service as generation_service 

# Configure structured logging
logger = logging.getLogger("app.api.cases")

router = APIRouter()

# -----------------------------------------------------------------------------
# Constants & Configuration
# -----------------------------------------------------------------------------
# Regex for safe filenames (alphanumeric, dashes, underscores, spaces)
SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\. ]+$")

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
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
) -> List[Case]:
    """
    Fetches cases using SQLAlchemy 2.0 syntax.
    Relies on RLS (Row Level Security) applied by `get_db` or query filtering.
    """
    stmt = (
        select(Case)
        .options(selectinload(Case.client)) # efficient for collections
        .order_by(Case.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


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
    Optimized to avoid loading heavy relationships.
    """
    # 1. Fetch Case Status Only
    case_status = db.scalar(
        select(Case.status).where(Case.id == case_id)
    )
    if not case_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Case not found"
        )
    
    # 2. Fetch Lightweight Document List (ID + Status Only)
    # This avoids loading the full Document object (which might have large text fields in future)
    docs_stmt = (
        select(Document.id, Document.ai_status, Document.created_at, Document.filename)
        .where(Document.case_id == case_id)
    )
    docs = db.execute(docs_stmt).all()
    
    # Map to schema format
    documents_data = [
        {
            "id": row.id, 
            "ai_status": row.ai_status, 
            "created_at": row.created_at,
            "filename": row.filename
        } 
        for row in docs
    ]

    # 3. Check for processing documents
    is_generating = (case_status == CaseStatus.GENERATING) or any(
        d["ai_status"] in [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING] for d in documents_data
    )
    
    return {
        "id": case_id,
        "status": case_status,
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
    current_user: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)]
) -> Case:
    """
    Creates a new case. Handles optional client creation via CRM service.
    """
    # Strict Type Parsing
    # Fetch User from DB to get Organization ID (Reliable Source of Truth)
    # Note: get_db dependency already ensures the user exists via RLS/Session setup,
    # but we need the actual ORM object here to access the relationship/field.
    user = db.get(User, current_user["uid"])
    if not user:
        # Should be caught by get_db, but safe guard
        raise HTTPException(status_code=403, detail="User account not found.")
        
    org_id = user.organization_id

    # CRM Logic
    client_id: Optional[UUID] = None
    if case_in.client_name:
        client = case_service.get_or_create_client(db, case_in.client_name, org_id)
        client_id = client.id

    new_case = Case(
        reference_code=case_in.reference_code,
        organization_id=org_id,
        client_id=client_id,
        status=CaseStatus.OPEN
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case


@router.get("/{case_id}", response_model=schemas.CaseDetail)
def get_case_detail(
    case_id: UUID, 
    db: Annotated[Session, Depends(get_db)]
) -> Case:
    """
    Retrieves full case details including documents and report versions.
    """
    stmt = (
        select(Case)
        .options(
            selectinload(Case.documents), 
            selectinload(Case.report_versions)
        )
        .where(Case.id == case_id)
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
    """
    Generates a secure, time-limited Signed URL for GCS uploads.
    Enforces MIME types and Organization isolation.
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Sanitize Filename
    clean_filename = Path(filename).name
    if not SAFE_FILENAME_REGEX.match(clean_filename):
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
    # Path: uploads/{org_id}/{case_id}/{clean_filename}
    return gcs_service.generate_upload_signed_url(
        org_id=str(case.organization_id),
        case_id=str(case.id),
        filename=clean_filename,
        content_type=content_type
    )


@router.post(
    "/{case_id}/documents/register", 
    response_model=schemas.DocumentRead
)
def register_document(
    case_id: UUID,
    payload: schemas.DocumentRegisterPayload, # Refactored to use Pydantic body
    db: Annotated[Session, Depends(get_db)]
) -> Document:
    """
    Registers a file uploaded to GCS in the database.
    
    Security: Strictly validates that the provided GCS path belongs 
    to the authenticated organization and case.
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Security: Path Validation (Prevent IDOR)
    # The path MUST start with: uploads/<org_id>/<case_id>/
    expected_prefix = f"uploads/{case.organization_id}/{case.id}/"
    
    # Strip potential 'gs://bucket/' prefix if sent by client
    clean_path = payload.gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
    
    if not clean_path.startswith(expected_prefix):
        logger.warning(f"IDOR Attempt: User tried to register path {clean_path} for case {case.id}")
        raise HTTPException(
            status_code=403, 
            detail="Security violation: File path does not match case context."
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
    db.commit()
    db.refresh(new_doc)
    
    # 3. Trigger Async Processing
    # Note: We do NOT pass 'db' here.
    case_service.trigger_extraction_task(new_doc.id, str(case.organization_id))
    
    return new_doc


@router.post("/{case_id}/generate")
async def trigger_generation(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)]
) -> dict:
    """
    Triggers the AI Report Generation pipeline.
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if settings.RUN_LOCALLY:
        # LOCAL DEV: Use BackgroundTasks
        # CRITICAL: Do NOT pass 'db' session. 
        # The service method must create a NEW session using SessionLocal()
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
    """
    Finalizes a case by promoting a specific DOCX as the official version.
    """
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Path Security & Traversal Protection
    raw_path = payload.final_docx_path
    
    # Check for traversal chars
    if ".." in raw_path or "~" in raw_path:
        raise HTTPException(status_code=403, detail="Invalid path characters.")

    # 2. Strict Prefix Validation
    # Allow files from 'uploads/' (user uploaded) or 'reports/' (system generated)
    clean_path = raw_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
    
    valid_prefixes = [
        f"uploads/{case.organization_id}/{case.id}/",
        f"reports/{case.organization_id}/{case.id}/"
    ]
    
    if not any(clean_path.startswith(prefix) for prefix in valid_prefixes):
        logger.warning(f"IDOR Attempt in finalize: {clean_path}")
        raise HTTPException(
            status_code=403, 
            detail="File must belong to this case (invalid path prefix)."
        )

    # 3. Execute Service
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
    """
    Generates a download URL.
    - Final versions: Direct GCS link.
    - Draft versions: Renders template on-the-fly.
    """
    # Validate Case
    case = db.get(Case, case_id)
    if not case:
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
