import logging
from pathlib import Path
from typing import Annotated, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
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
    description="Retrieve a paginated list of cases for the authenticated organization.",
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
            selectinload(Case.creator).load_only(User.email),
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
            (Case.reference_code.ilike(f"%{search}%"))
            | (Client.name.ilike(f"%{search}%"))
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
    summary="Get Case Status",
)
def get_case_status(case_id: UUID, db: Annotated[Session, Depends(get_db)]) -> dict:
    """
    Lightweight polling endpoint.
    Returns boolean status + granular progress stats.
    """
    # 1. Fetch Case Status
    case = db.scalar(select(Case).where(Case.id == case_id, Case.deleted_at.is_(None)))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # 2. Fetch Document Meta
    docs_stmt = select(
        Document.id, Document.ai_status, Document.created_at, Document.filename
    ).where(Document.case_id == case_id)
    docs = db.execute(docs_stmt).all()

    documents_data = [
        {
            "id": row.id,
            "ai_status": row.ai_status,
            "created_at": row.created_at,
            "filename": row.filename,
        }
        for row in docs
    ]

    # 3. Calculate Processing State
    is_generating = (case.status == CaseStatus.GENERATING) or any(
        d["ai_status"] in [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING]
        for d in documents_data
    )

    return {
        "id": case_id,
        "status": case.status,
        "documents": documents_data,
        "is_generating": is_generating,
    }


@router.post(
    "/",
    response_model=schemas.CaseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create Case",
)
def create_case(
    case_in: schemas.CaseCreate,
    current_user: Annotated[dict[str, Any], Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)],
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
        user_org_id=user.organization_id,  # Pass the Object UUID
    )


@router.get("/{case_id}", response_model=schemas.CaseDetail)
def get_case_detail(case_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Case:
    stmt = (
        select(Case)
        .options(
            selectinload(Case.documents),
            selectinload(Case.report_versions),
            selectinload(Case.creator).load_only(User.email),
        )
        .where(Case.id == case_id, Case.deleted_at.is_(None))
    )
    case = db.scalar(stmt)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case



@router.patch("/{case_id}", response_model=schemas.CaseDetail)
def update_case(
    case_id: UUID,
    update_data: schemas.CaseUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Case:
    """
    Update case fields. Supports partial updates (PATCH).

    If client_name is provided, performs fuzzy matching against existing clients
    or creates a new one.
    """
    from app.services.client_matcher import find_or_create_client

    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get update data (exclude None values for partial update)
    update_dict = update_data.model_dump(exclude_unset=True)

    # Handle client_name specially - fuzzy match or create
    if "client_name" in update_dict:
        client_name = update_dict.pop("client_name")
        if client_name:
            client = find_or_create_client(db, case.organization_id, client_name)
            if client:
                case.client_id = client.id

    # Apply all other updates
    for field, value in update_dict.items():
        if hasattr(case, field):
            setattr(case, field, value)

    db.commit()

    # Re-apply RLS context before refresh
    from sqlalchemy import text

    try:
        db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"),
            {"oid": str(case.organization_id)},
        )
    except Exception as e:
        logger.warning(f"Failed to re-apply RLS context: {e}")

    db.refresh(case)

    logger.info(f"Updated case {case_id} with fields: {list(update_dict.keys())}")
    return case


@router.post("/{case_id}/documents/upload-url")
def get_doc_upload_url(
    case_id: UUID,
    filename: str,
    content_type: str,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Sanitize Filename (Accept all characters, sanitize for storage)
    # Import the robust sanitizer that handles special chars like apostrophes and accents
    from app.services.document_processor import sanitize_filename

    # Keep original for extension detection, apply sanitization for storage
    original_basename = Path(filename).name
    clean_filename = sanitize_filename(original_basename)

    # Ensure we still have a valid filename after sanitization
    if not clean_filename or clean_filename == ".":
        clean_filename = "document"

    # Preserve the original extension
    ext = Path(original_basename).suffix.lower()
    if ext and not clean_filename.endswith(ext):
        clean_filename = Path(clean_filename).stem + ext

    # 2. Validate Extension & MIME
    if ext not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file extension: {ext}"
        )

    if content_type != settings.ALLOWED_MIME_TYPES[ext]:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type mismatch. Expected {settings.ALLOWED_MIME_TYPES[ext]}.",
        )

    # 3. Generate URL
    return gcs_service.generate_upload_signed_url(
        filename=clean_filename,
        content_type=content_type,
        organization_id=str(case.organization_id),
        case_id=str(case.id),
    )


@router.post("/{case_id}/documents/register", response_model=schemas.DocumentRead)
def register_document(
    case_id: UUID,
    payload: schemas.DocumentRegisterPayload,
    db: Annotated[Session, Depends(get_db)],
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
        allowed_prefixes=["uploads"],
    )

    # 2. Create Record
    new_doc = Document(
        case_id=case.id,
        organization_id=case.organization_id,
        filename=payload.filename,
        gcs_path=clean_path,
        mime_type=payload.mime_type,
        ai_status=ExtractionStatus.PENDING,
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
            detail="Failed to finalize document storage.",
        ) from e

    # 3. Commit only if tagging succeeded (or we are okay with it, but here we enforce it)
    db.commit()

    # RE-APPLY RLS CONTEXT (Fix for QueuePool connection swap after commit)
    # db.commit() may release connection to pool, and db.refresh() gets a new one
    # without the RLS session variables set.
    from sqlalchemy import text

    try:
        db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"),
            {"oid": str(case.organization_id)},
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
    db: Annotated[Session, Depends(get_db)],
    payload: Optional[schemas.GeneratePayload] = None,
) -> dict:
    import asyncio

    # Extract language and extra_instructions from payload (defaults)
    language = payload.language if payload else "italian"
    extra_instructions = payload.extra_instructions if payload else None

    # PERF FIX: Wrap sync DB operations in asyncio.to_thread()
    def _get_case_and_update_status():
        case = db.get(Case, case_id)
        if not case or case.deleted_at:
            return None
        case.status = CaseStatus.GENERATING
        db.commit()
        return case

    case = await asyncio.to_thread(_get_case_and_update_status)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if settings.RUN_LOCALLY:
        # LOCAL DEV
        background_tasks.add_task(
            generation_service.run_generation_task,
            case_id=str(case.id),
            organization_id=str(case.organization_id),
            language=language,
            extra_instructions=extra_instructions,
        )
    else:
        # PROD: Cloud Tasks
        await generation_service.trigger_generation_task(
            str(case.id),
            str(case.organization_id),
            language=language,
            extra_instructions=extra_instructions,
        )

    return {"status": "generation_started"}


@router.post("/{case_id}/finalize", response_model=schemas.VersionRead)
def finalize_case_endpoint(
    case_id: UUID,
    payload: schemas.FinalizePayload,
    db: Annotated[Session, Depends(get_db)],
) -> ReportVersion:
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Validated Path
    clean_path = case_service.validate_storage_path(
        raw_path=payload.final_docx_path,
        org_id=case.organization_id,
        case_id=case.id,
        allowed_prefixes=["uploads", "reports"],
    )

    # 2. Execute Service
    final_version: ReportVersion = case_service.finalize_case(
        db=db, case_id=case.id, org_id=case.organization_id, final_docx_path=clean_path
    )

    return final_version


@router.post("/{case_id}/versions/{version_id}/download")
async def download_version(
    case_id: UUID,
    version_id: UUID,
    payload: schemas.DownloadVariantPayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user_token)],
) -> dict:
    import asyncio

    # PERF FIX: Wrap sync DB operations in asyncio.to_thread()
    def _validate_case_and_version():
        case = db.get(Case, case_id)
        if not case or case.deleted_at:
            return None, None
        stmt = select(ReportVersion).where(
            ReportVersion.id == version_id, ReportVersion.case_id == case_id
        )
        version = db.scalar(stmt)
        return case, version

    case, version = await asyncio.to_thread(_validate_case_and_version)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        if version.is_final:
            if not version.docx_storage_path:
                raise HTTPException(status_code=404, detail="File path missing.")

            # PERF FIX: Wrap sync GCS call in asyncio.to_thread()
            url = await asyncio.to_thread(
                gcs_service.generate_download_signed_url, version.docx_storage_path
            )
            return {"download_url": url}
        else:
            # Generate variant logic (already async)
            url = await generation_service.generate_docx_variant(
                version_id=str(version_id), template_type=payload.template_type, db=db
            )
            return {"download_url": url}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Download generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


def _delete_case_folders(org_id: str, case_id: str) -> int:
    """
    Safety net: Delete all files in case-specific GCS folders.
    Catches untracked files (artifacts, unregistered uploads from crashed flows).

    Returns count of deleted objects.
    """
    from google.cloud import storage  # type: ignore[attr-defined]

    client = storage.Client()
    bucket = client.bucket(settings.STORAGE_BUCKET_NAME)
    deleted = 0

    # Delete uploads folder (raw files + artifacts)
    uploads_prefix = f"uploads/{org_id}/{case_id}/"
    for blob in bucket.list_blobs(prefix=uploads_prefix):
        blob.delete()
        deleted += 1

    # Delete reports folder
    reports_prefix = f"reports/{org_id}/{case_id}/"
    for blob in bucket.list_blobs(prefix=reports_prefix):
        blob.delete()
        deleted += 1

    if deleted > 0:
        logger.info(
            f"Safety net deleted {deleted} additional GCS files for case {case_id}"
        )

    return deleted


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: UUID, db: Annotated[Session, Depends(get_db)]):
    """
    Soft-deletes a case and hard-deletes all associated documents and report versions from GCS.
    """
    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    org_id = str(case.organization_id)
    case_id_str = str(case_id)

    # 1. Delete all documents from GCS and DB
    docs = db.scalars(select(Document).where(Document.case_id == case_id)).all()
    for doc in docs:
        if doc.gcs_path:
            try:
                gcs_service.delete_blob(doc.gcs_path)
                logger.info(f"Deleted GCS blob: {doc.gcs_path}")
            except Exception as e:
                logger.warning(f"Failed to delete GCS blob {doc.gcs_path}: {e}")
        db.delete(doc)

    # 2. Delete all report versions from GCS and DB
    versions = db.scalars(
        select(ReportVersion).where(ReportVersion.case_id == case_id)
    ).all()
    for v in versions:
        if v.docx_storage_path:
            try:
                gcs_service.delete_blob(v.docx_storage_path)
                logger.info(f"Deleted GCS blob: {v.docx_storage_path}")
            except Exception as e:
                logger.warning(f"Failed to delete GCS blob {v.docx_storage_path}: {e}")
        db.delete(v)

    # 3. Safety net: Delete entire case folders to catch untracked files
    try:
        _delete_case_folders(org_id, case_id_str)
    except Exception as e:
        logger.warning(f"Failed to delete case folders from GCS: {e}")

    # 4. Soft-delete the case
    from datetime import datetime, timezone

    case.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        f"Case {case_id} soft-deleted with {len(docs)} docs and {len(versions)} versions removed."
    )
    return


@router.delete("/{case_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    case_id: UUID, doc_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    """
    Hard-deletes a single document from DB and GCS.
    """
    # Verify document belongs to case
    doc = db.scalar(
        select(Document).where(Document.id == doc_id, Document.case_id == case_id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from GCS
    if doc.gcs_path:
        try:
            gcs_service.delete_blob(doc.gcs_path)
            logger.info(f"Deleted GCS blob: {doc.gcs_path}")
        except Exception as e:
            logger.warning(f"Failed to delete GCS blob {doc.gcs_path}: {e}")

    # Hard delete from DB
    db.delete(doc)
    db.commit()
    logger.info(f"Document {doc_id} deleted from case {case_id}.")
    return


# -----------------------------------------------------------------------------
# Early Analysis Feature: Documents List & Document Analysis
# -----------------------------------------------------------------------------

# MIME types that support inline preview
PREVIEWABLE_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


@router.get(
    "/{case_id}/documents",
    response_model=schemas.DocumentsListResponse,
    summary="List Documents",
    description="Get all documents for a case with signed URLs for preview/download.",
)
async def list_documents(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Returns all documents for a case with:
    - Signed URLs for preview/download
    - Preview capability flag based on MIME type
    - Extraction status
    """
    import asyncio

    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # Fetch all documents
    docs = db.scalars(
        select(Document)
        .where(Document.case_id == case_id)
        .order_by(Document.created_at.desc())
    ).all()

    # Count pending documents
    pending_count = sum(
        1
        for d in docs
        if d.ai_status in [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING]
    )

    # Generate signed URLs (wrap sync call)
    def build_document_list():
        result = []
        for doc in docs:
            url = None
            if doc.gcs_path:
                try:
                    url = gcs_service.generate_download_signed_url(doc.gcs_path)
                except Exception as e:
                    logger.warning(f"Failed to generate signed URL for {doc.id}: {e}")

            can_preview = (
                doc.mime_type in PREVIEWABLE_MIME_TYPES if doc.mime_type else False
            )

            result.append(
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "mime_type": doc.mime_type,
                    "status": doc.ai_status,
                    "can_preview": can_preview,
                    "url": url,
                }
            )
        return result

    documents_list = await asyncio.to_thread(build_document_list)

    return {
        "documents": documents_list,
        "total": len(docs),
        "pending_extraction": pending_count,
    }


@router.get(
    "/{case_id}/document-analysis",
    response_model=schemas.DocumentAnalysisResponse,
    summary="Get Document Analysis",
    description="Retrieve the latest document analysis for a case.",
)
async def get_document_analysis(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Returns the most recent document analysis for a case, if it exists.
    Also indicates whether a new analysis can be triggered (no pending docs).
    """


    from app.db.database import AsyncSessionLocal
    from app.services import document_analysis_service

    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # Use async session for async service calls
    async with AsyncSessionLocal() as async_db:
        # Set RLS context
        from sqlalchemy import text

        await async_db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"),
            {"oid": str(case.organization_id)},
        )

        # Get analysis and check staleness
        is_stale, analysis = await document_analysis_service.check_analysis_staleness(
            case_id, async_db
        )

        # Check for pending documents
        has_pending, pending_count = (
            await document_analysis_service.check_has_pending_documents(
                case_id, async_db
            )
        )

    response = {
        "analysis": analysis,
        "can_update": not has_pending,
        "pending_docs": pending_count,
    }

    return response


@router.post(
    "/{case_id}/document-analysis",
    response_model=schemas.DocumentAnalysisCreateResponse,
    summary="Run Document Analysis",
    description="Trigger AI analysis of uploaded documents.",
)
async def create_document_analysis(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    payload: Optional[schemas.DocumentAnalysisRequest] = None,
) -> dict:
    """
    Runs AI document analysis using Gemini.

    Returns cached analysis if not stale (unless force=True).
    Blocks if documents are still being processed.
    """
    from sqlalchemy import text

    from app.db.database import AsyncSessionLocal
    from app.services import document_analysis_service

    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    force = payload.force if payload else False

    # Use async session for async service calls
    async with AsyncSessionLocal() as async_db:
        # Set RLS context
        await async_db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"),
            {"oid": str(case.organization_id)},
        )

        try:
            # Check if we can return cached version
            if not force:
                is_stale, existing = (
                    await document_analysis_service.check_analysis_staleness(
                        case_id, async_db
                    )
                )
                if existing and not is_stale:
                    logger.info(f"Returning cached analysis for case {case_id}")
                    return {"analysis": existing, "generated": False}

            # Run the analysis
            analysis = await document_analysis_service.run_document_analysis(
                case_id=case_id,
                org_id=case.organization_id,
                db=async_db,
                force=force,
            )

            return {"analysis": analysis, "generated": True}

        except document_analysis_service.AnalysisBlockedError as e:
            logger.warning(f"Analysis blocked for case {case_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from None

        except document_analysis_service.AnalysisGenerationError as e:
            logger.error(f"Analysis generation failed for case {case_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Analysis generation failed, please retry.",
            ) from None


# =============================================================================
# PRELIMINARY REPORT ENDPOINTS
# =============================================================================


@router.get(
    "/{case_id}/preliminary",
    response_model=schemas.PreliminaryReportResponse,
    summary="Get Preliminary Report",
    description="Retrieve the latest preliminary report for a case.",
)
async def get_preliminary_report(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Returns the most recent preliminary report for a case, if it exists.
    Also indicates whether a new report can be generated (no pending docs).
    """


    from app.db.database import AsyncSessionLocal
    from app.services import preliminary_report_service

    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    # Use async session for async service calls
    async with AsyncSessionLocal() as async_db:
        # Set RLS context
        from sqlalchemy import text

        await async_db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"),
            {"oid": str(case.organization_id)},
        )

        # Get existing report
        report = await preliminary_report_service.get_latest_preliminary_report(
            case_id, async_db
        )

        # Check for pending documents
        has_pending, pending_count = (
            await preliminary_report_service.check_has_pending_documents(
                case_id, async_db
            )
        )

        # Build response with mapped fields
        report_data = None
        if report:
            report_data = {
                "id": report.id,
                "content": report.ai_raw_output or "",
                "created_at": report.created_at,
            }

        return {
            "report": report_data,
            "can_generate": not has_pending,
            "pending_docs": pending_count,
        }


@router.post(
    "/{case_id}/preliminary",
    response_model=schemas.PreliminaryReportCreateResponse,
    summary="Generate Preliminary Report",
    description="Generate an AI preliminary report for a case.",
    status_code=status.HTTP_200_OK,
)
async def create_preliminary_report(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    request: schemas.PreliminaryReportRequest = schemas.PreliminaryReportRequest(),
) -> dict:
    """
    Trigger AI preliminary report generation.

    - Returns 409 if documents are still being processed
    - Returns 200 with generated=False if returning cached (unless force=True)
    - Returns 200 with generated=True if new report was generated
    """


    from app.db.database import AsyncSessionLocal
    from app.services import preliminary_report_service

    case = db.get(Case, case_id)
    if not case or case.deleted_at:
        raise HTTPException(status_code=404, detail="Case not found")

    force = request.force if request else False

    async with AsyncSessionLocal() as async_db:
        # Set RLS context
        from sqlalchemy import text

        await async_db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"),
            {"oid": str(case.organization_id)},
        )

        try:
            # Check if we can return cached version
            if not force:
                existing = (
                    await preliminary_report_service.get_latest_preliminary_report(
                        case_id, async_db
                    )
                )
                if existing:
                    logger.info(
                        f"Returning cached preliminary report for case {case_id}"
                    )
                    return {
                        "report": {
                            "id": existing.id,
                            "content": existing.ai_raw_output or "",
                            "created_at": existing.created_at,
                        },
                        "generated": False,
                    }

            # Run the report generation
            report = await preliminary_report_service.run_preliminary_report(
                case_id=case_id,
                org_id=case.organization_id,
                db=async_db,
                force=force,
            )

            return {
                "report": {
                    "id": report.id,
                    "content": report.ai_raw_output or "",
                    "created_at": report.created_at,
                },
                "generated": True,
            }

        except preliminary_report_service.PreliminaryBlockedError as e:
            logger.warning(f"Preliminary report blocked for case {case_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from None

        except preliminary_report_service.PreliminaryReportError as e:
            logger.error(
                f"Preliminary report generation failed for case {case_id}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Report generation failed, please retry.",
            ) from None
