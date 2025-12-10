"""Google Docs Live Draft API endpoints.

Isolated router for easy rollback.
"""

import asyncio
import io
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user_token, get_db
from app.core.config import settings
from app.models import ReportVersion
from app.services import case_service
from app.services.drive_service import DriveService, get_drive_service
from app.services.gcs_service import get_storage_client

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request/Response Models ---


class OpenInDocsRequest(BaseModel):
    template: Literal["bn", "salomone"]


class OpenInDocsResponse(BaseModel):
    url: str
    file_id: str


class ConfirmDocsResponse(BaseModel):
    message: str
    version_id: str


# --- Endpoints ---


@router.post(
    "/cases/{case_id}/versions/{version_id}/open-in-docs",
    response_model=OpenInDocsResponse,
    summary="Open report in Google Docs for editing",
)
async def open_in_docs(
    case_id: UUID,
    version_id: UUID,
    payload: OpenInDocsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_token),
    drive: DriveService = Depends(get_drive_service),
):
    """
    Creates a new Google Doc from the report version for editing.
    If a draft already exists with the SAME template, returns the existing link.
    If template differs, creates a new draft.
    """
    # 1. Fetch version with case (eager load to avoid lazy-load issues)
    stmt = (
        select(ReportVersion)
        .options(joinedload(ReportVersion.case))
        .where(ReportVersion.id == version_id)
    )
    version = db.scalar(stmt)

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # 2. IDOR check: version must belong to case
    if version.case_id != case_id:
        raise HTTPException(
            status_code=403, detail="Version does not belong to this case"
        )

    # 3. If draft already active with SAME template, return existing link
    if (
        version.is_draft_active
        and version.edit_link
        and version.template_used == payload.template
    ):
        return OpenInDocsResponse(
            url=version.edit_link, file_id=version.google_doc_id or ""
        )

    # 4. Generate DOCX using existing pattern
    if not version.ai_raw_output:
        raise HTTPException(
            status_code=400, detail="No AI content found for this version"
        )

    try:
        # If switching templates and old draft exists, delete it first
        if (
            version.is_draft_active
            and version.google_doc_id
            and version.template_used != payload.template
        ):
            try:
                await asyncio.to_thread(drive.delete_file, version.google_doc_id)
                logger.info(
                    f"Deleted old draft {version.google_doc_id} due to template change"
                )
            except Exception as e:
                logger.warning(f"Failed to delete old draft: {e}")

        # Generate DOCX with selected template (reuse existing pattern)
        if payload.template == "salomone":
            from app.services import docx_generator_salomone

            docx_stream = await asyncio.to_thread(
                docx_generator_salomone.create_styled_docx, version.ai_raw_output
            )
        else:
            from app.services import docx_generator

            docx_stream = await asyncio.to_thread(
                docx_generator.create_styled_docx, version.ai_raw_output
            )

        # 5. Upload to Google Docs
        filename = f"{version.case.reference_code}_v{version.version_number}"
        result = await asyncio.to_thread(
            drive.create_editable_draft, docx_stream, filename
        )

        # 6. Update version record
        version.google_doc_id = result["file_id"]
        version.edit_link = result["url"]
        version.is_draft_active = True
        version.template_used = payload.template
        db.commit()

        # Re-apply RLS context after commit (connection pool may swap)
        try:
            db.execute(
                text("SELECT set_config('app.current_org_id', :oid, false)"),
                {"oid": str(version.organization_id)},
            )
        except Exception as e:
            logger.warning(f"Failed to re-apply RLS context: {e}")

        logger.info(
            f"Created Google Doc draft for version {version_id}: {result['file_id']}"
        )

        return OpenInDocsResponse(url=result["url"], file_id=result["file_id"])

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create Google Doc: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create Google Doc: {str(e)}",
        )


@router.post(
    "/cases/{case_id}/versions/{version_id}/confirm-docs",
    response_model=ConfirmDocsResponse,
    summary="Confirm Google Docs edits and finalize case",
)
async def confirm_docs(
    case_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_token),
    drive: DriveService = Depends(get_drive_service),
):
    """
    Exports the edited document from Google Docs, saves to GCS,
    and finalizes the case.
    """
    # 1. Fetch version
    stmt = (
        select(ReportVersion)
        .options(joinedload(ReportVersion.case))
        .where(ReportVersion.id == version_id)
    )
    version = db.scalar(stmt)

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # 2. IDOR check
    if version.case_id != case_id:
        raise HTTPException(
            status_code=403, detail="Version does not belong to this case"
        )

    # 3. Check draft is active
    if not version.is_draft_active or not version.google_doc_id:
        raise HTTPException(status_code=400, detail="No active draft to confirm")

    try:
        # 4. Export from Google Docs and delete temp file
        docx_bytes = await asyncio.to_thread(
            drive.export_and_delete, version.google_doc_id
        )

        # 5. Upload to GCS
        bucket_name = settings.STORAGE_BUCKET_NAME
        blob_name = f"reports/{version.organization_id}/{version.case_id}/final_v{version.version_number}.docx"

        def upload_final():
            storage_client = get_storage_client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(
                io.BytesIO(docx_bytes),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            return f"gs://{bucket_name}/{blob_name}"

        gcs_path = await asyncio.to_thread(upload_final)

        # 6. Finalize case using existing service (wrapped in thread for sync function)
        final_version = await asyncio.to_thread(
            case_service.finalize_case,
            db=db,
            case_id=case_id,
            org_id=version.organization_id,
            final_docx_path=gcs_path,
        )

        # 7. Clear draft state on original version
        version.is_draft_active = False
        version.google_doc_id = None
        version.edit_link = None
        db.commit()

        # Re-apply RLS context after commit
        try:
            db.execute(
                text("SELECT set_config('app.current_org_id', :oid, false)"),
                {"oid": str(version.organization_id)},
            )
        except Exception as e:
            logger.warning(f"Failed to re-apply RLS context: {e}")

        logger.info(
            f"Confirmed Google Docs edits for case {case_id}, created final version {final_version.id}"
        )

        return ConfirmDocsResponse(
            message="Case finalized successfully", version_id=str(final_version.id)
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to confirm Google Docs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync from Google Docs: {str(e)}",
        )
