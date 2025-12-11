import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select, union
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_raw_db, get_superadmin_user
from app.models import AllowedEmail, Case, Document, Organization, ReportVersion, User
from app.schemas.enums import CaseStatus, UserRole

# Configure Structured Logging
logger = logging.getLogger("app.admin.orgs")

router = APIRouter()

# ============= Request/Response Models =============


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    def strip_whitespace(cls, v: str):
        return v.strip()


class OrganizationResponse(OrganizationBase):
    id: uuid.UUID
    created_at: str

    # Pydantic V2 Config for ORM mode
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", mode="before")
    def serialize_datetime(cls, v):
        return v.isoformat() if v else None


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER

    @field_validator("email")
    def normalize_email(cls, v: str):
        return v.lower().strip()


class AllowedEmailResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    organization_id: uuid.UUID
    created_at: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", mode="before")
    def serialize_datetime(cls, v):
        return v.isoformat() if v else None


class GenericMessage(BaseModel):
    message: str


# ============= Stats Response Models =============


class CaseCountsByStatus(BaseModel):
    """Count of cases grouped by status."""

    OPEN: int = 0
    CLOSED: int = 0
    ERROR: int = 0
    GENERATING: int = 0
    PROCESSING: int = 0
    ARCHIVED: int = 0


class UserSummary(BaseModel):
    """Lightweight user info for dropdowns."""

    id: str  # Firebase UID - string, not UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class GlobalStatsResponse(BaseModel):
    """Platform-wide statistics for superadmin."""

    org_count: int
    user_count: int
    case_counts: CaseCountsByStatus
    document_count: int
    report_count: int
    gcs_bucket_size_gb: float | None = None  # Optional - may timeout


class OrgStatsResponse(BaseModel):
    """Organization-level statistics."""

    org_id: str
    org_name: str
    user_count: int
    case_counts: CaseCountsByStatus
    document_count: int
    users: list[UserSummary]


class UserStatsResponse(BaseModel):
    """Individual user statistics."""

    user_id: str  # Firebase UID
    user_email: str
    total_cases: int
    cases_today: int
    cases_last_7_days: int
    cases_by_status: CaseCountsByStatus


# ============= Endpoints =============


@router.get(
    "/organizations",
    response_model=List[OrganizationResponse],
    summary="List Organizations",
    description="Retrieve a list of all registered organizations.",
)
def list_organizations(
    superadmin: User = Depends(get_superadmin_user), db: Session = Depends(get_raw_db)
) -> List[Organization]:
    """
    Superadmin only: List all organizations.
    """
    # Modern SQLAlchemy 2.0 syntax
    stmt = select(Organization).order_by(Organization.name)
    return list(db.scalars(stmt).all())


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
)
def create_organization(
    request: OrganizationBase,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_raw_db),
) -> Organization:
    """
    Superadmin only: Create a new organization.
    """
    try:
        new_org = Organization(name=request.name)
        db.add(new_org)
        db.commit()
        db.refresh(new_org)
        logger.info(f"Organization created: {new_org.name} by {superadmin.email}")
        return new_org

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this name likely already exists.",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error",
        )


@router.get(
    "/organizations/{org_id}/invites",
    response_model=List[AllowedEmailResponse],
    summary="List Invites",
)
def list_org_invites(
    org_id: uuid.UUID,  # FastAPI automatically validates UUID format here
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_raw_db),
) -> List[AllowedEmail]:
    """
    Superadmin only: List all whitelisted emails for an organization.
    """
    # Verify org exists first
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    stmt = select(AllowedEmail).where(AllowedEmail.organization_id == org_id)
    return list(db.scalars(stmt).all())


@router.post(
    "/organizations/{org_id}/users/invite",
    response_model=GenericMessage,
    status_code=status.HTTP_201_CREATED,
    summary="Invite User",
)
def invite_user_to_org(
    org_id: uuid.UUID,
    request: InviteUserRequest,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_raw_db),
) -> GenericMessage:
    """
    Superadmin only: Whitelist an email for a specific organization.
    """
    # 1. Validation: Organization
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    # 2. Validation: Already Whitelisted?
    # Uses 'select' with 'limit(1)' implicitly via scalar_one_or_none logic usually,
    # but scalar() works efficiently here.
    invite_stmt = select(AllowedEmail).where(AllowedEmail.email == request.email)
    if db.scalar(invite_stmt):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already whitelisted."
        )

    # 3. Validation: User Already Exists?
    user_stmt = select(User).where(User.email == request.email)
    if db.scalar(user_stmt):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already registered in the system.",
        )

    # 4. Action: Create Invite
    try:
        new_invite = AllowedEmail(
            organization_id=org_id, email=request.email, role=request.role.value
        )
        db.add(new_invite)
        db.commit()

        logger.info(f"Invite created: {request.email} -> Org {org_id}")
        return GenericMessage(message=f"User {request.email} invited to {org.name}")

    except Exception as e:
        db.rollback()
        logger.error(f"Invite failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process invite.",
        )


@router.delete(
    "/invites/{invite_id}", response_model=GenericMessage, summary="Revoke Invite"
)
def delete_invite(
    invite_id: uuid.UUID,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_raw_db),
) -> GenericMessage:
    """
    Superadmin only: Remove a whitelisted email.
    """
    invite = db.get(AllowedEmail, invite_id)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )

    try:
        db.delete(invite)
        db.commit()
        logger.info(f"Invite revoked: {invite.email}")
        return GenericMessage(message="Invite removed successfully")
    except Exception as e:
        db.rollback()
        logger.error(f"Revoke failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete invite.",
        )


@router.post(
    "/storage/cleanup", response_model=dict, summary="Cleanup Orphaned GCS Files"
)
def cleanup_orphaned_storage(
    superadmin: User = Depends(get_superadmin_user), db: Session = Depends(get_raw_db)
) -> dict:
    """
    Superadmin only: Deletes orphaned files from GCS uploads/ directory.

    Source of Truth: Postgres (Document and ReportVersion tables).
    Only deletes files that are > 24 hours old AND do not exist in the DB.
    """

    from datetime import datetime, timedelta, timezone

    from app.core.config import settings
    from app.services import gcs_service

    # Document, ReportVersion, union are now top-level imports

    try:
        start_time = datetime.now(timezone.utc)
        # Cloud Run Timeout Safety: Stop processing after 50 seconds
        TIME_LIMIT_SECONDS = 50

        client = gcs_service.get_storage_client()
        bucket = client.bucket(settings.STORAGE_BUCKET_NAME)

        blobs = bucket.list_blobs(prefix="uploads/")

        deleted_count = 0
        skipped_count = 0
        partial_complete = False

        cutoff_time = start_time - timedelta(hours=24)

        batch_paths = []
        blobs_to_check = []
        BATCH_SIZE = 100

        def process_batch(paths_batch: List[str], blobs_batch: List[Any]):
            nonlocal deleted_count
            if not paths_batch:
                return

            stmt: Any = union(
                select(Document.gcs_path).where(Document.gcs_path.in_(paths_batch)),
                select(ReportVersion.docx_storage_path).where(
                    ReportVersion.docx_storage_path.in_(paths_batch)
                ),
            )
            valid_paths = set(db.scalars(stmt).all())

            for b in blobs_batch:
                if b.name not in valid_paths:
                    logger.info(f"Deleting orphan: {b.name}")
                    try:
                        b.delete()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {b.name}: {e}")

        for blob in blobs:
            # Check Time Budget
            if (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() > TIME_LIMIT_SECONDS:
                logger.warning("Cleanup job hitting time limit. Stopping early.")
                partial_complete = True
                break

            if blob.time_created < cutoff_time:
                batch_paths.append(blob.name)
                blobs_to_check.append(blob)

                if len(batch_paths) >= BATCH_SIZE:
                    process_batch(batch_paths, blobs_to_check)
                    skipped_count += len(batch_paths) - (
                        len(batch_paths) - len(blobs_to_check)
                    )
                    batch_paths = []
                    blobs_to_check = []
            else:
                skipped_count += 1

        if batch_paths:
            process_batch(batch_paths, blobs_to_check)

        logger.info(
            f"Storage cleanup completed: {deleted_count} deleted. Partial: {partial_complete}"
        )

        return {
            "status": "partial_success" if partial_complete else "success",
            "deleted_count": deleted_count,
            "cutoff_time": cutoff_time.isoformat(),
            "partial": partial_complete,
        }

    except Exception as e:
        logger.error(f"Storage cleanup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup operation failed: {str(e)}",
        )


@router.post("/rescue-zombies", response_model=dict, summary="Rescue Stuck Cases")
def rescue_stuck_cases(
    superadmin: User = Depends(get_superadmin_user), db: Session = Depends(get_raw_db)
) -> dict:
    """
    Superadmin only: Reset cases stuck in 'GENERATING' or 'PROCESSING' state for > 2 hours.

    These "zombie" cases occur if a worker crashes (OOM/Timeout) before updating the status.
    This endpoint finds them and resets them to OPEN so users can retry.
    """
    try:
        # Define cutoff time (2 hours ago - generous to avoid false positives)
        # NOTE: Using created_at instead of updated_at since cases table has no updated_at column
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)

        # SCALABILITY FIX: Use Bulk Update instead of Fetch-Loop-Save
        # This prevents loading thousands of objects into memory.
        from sqlalchemy import update

        stmt = (
            update(Case)
            .where(
                Case.status.in_([CaseStatus.GENERATING, CaseStatus.PROCESSING]),
                Case.created_at < cutoff_time,
            )
            .values(status=CaseStatus.OPEN)  # Reset to OPEN so users can retry
        )

        result = db.execute(stmt)
        rescued_count: int = result.rowcount or 0  # type: ignore
        db.commit()

        logger.info(f"Zombie rescue completed: {rescued_count} cases reset to OPEN")

        return {
            "status": "success",
            "rescued_count": rescued_count,
            "cutoff_time": cutoff_time.isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Zombie rescue failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rescue operation failed: {str(e)}",
        )


@router.post(
    "/reprocess-pending-documents",
    response_model=dict,
    summary="Reprocess Pending Documents",
)
def reprocess_pending_documents(
    superadmin: User = Depends(get_superadmin_user), db: Session = Depends(get_raw_db)
) -> dict:
    """
    Superadmin only: Re-enqueue Cloud Tasks for all documents stuck in PENDING status.

    Use this after fixing Cloud Tasks authentication issues to process documents
    that got stuck because their original tasks exhausted retries.
    """
    from app.schemas.enums import ExtractionStatus
    from app.services import case_service

    try:
        # Find all PENDING documents
        pending_docs = (
            db.query(Document)
            .filter(Document.ai_status == ExtractionStatus.PENDING.value)
            .all()
        )

        if not pending_docs:
            return {
                "status": "success",
                "message": "No pending documents found",
                "requeued_count": 0,
            }

        requeued_count = 0
        errors = []

        for doc in pending_docs:
            try:
                case_service.trigger_extraction_task(doc.id, str(doc.organization_id))
                requeued_count += 1
                logger.info(f"Requeued extraction task for document {doc.id}")
            except Exception as e:
                errors.append({"doc_id": str(doc.id), "error": str(e)})
                logger.error(f"Failed to requeue document {doc.id}: {e}")

        return {
            "status": "success",
            "requeued_count": requeued_count,
            "total_pending": len(pending_docs),
            "errors": errors[:10],  # Limit to first 10 errors
        }

    except Exception as e:
        logger.error(f"Reprocess pending documents failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reprocess operation failed: {str(e)}",
        )


# ============= Stats Helper Functions =============


def _get_case_counts_by_status(
    db: Session,
    org_id: uuid.UUID | None = None,
    user_id: str | None = None,
) -> CaseCountsByStatus:
    """
    Efficient aggregation query for case counts grouped by status.
    Optionally filter by organization or user.
    """
    query = db.query(Case.status, func.count(Case.id)).filter(Case.deleted_at.is_(None))

    if org_id:
        query = query.filter(Case.organization_id == org_id)
    if user_id:
        query = query.filter(Case.creator_id == user_id)

    results = query.group_by(Case.status).all()

    # Initialize with zeros
    counts = {status.value: 0 for status in CaseStatus}
    for case_status, count in results:
        # case_status might be CaseStatus enum or string depending on DB
        key = case_status.value if hasattr(case_status, "value") else case_status
        counts[key] = count

    return CaseCountsByStatus(**counts)


def _get_bucket_size_gb_safe(timeout_seconds: float = 5.0) -> float | None:
    """
    Returns GCS bucket size in GB, or None if timeout/error.
    Uses a timeout to prevent blocking on large buckets.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    from app.core.config import settings
    from app.services import gcs_service

    def calculate_size() -> float:
        client = gcs_service.get_storage_client()
        bucket = client.bucket(settings.STORAGE_BUCKET_NAME)
        total_bytes = sum(blob.size or 0 for blob in bucket.list_blobs())
        return round(total_bytes / (1024**3), 2)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(calculate_size)
            return future.result(timeout=timeout_seconds)
    except (FuturesTimeout, Exception) as e:
        logger.warning(f"GCS bucket size calculation timed out or failed: {e}")
        return None


# ============= Stats Endpoints =============


@router.get(
    "/stats",
    response_model=GlobalStatsResponse,
    summary="Get Global Platform Stats",
    description="Superadmin only: Get platform-wide statistics.",
)
def get_global_stats(
    superadmin: User = Depends(get_superadmin_user), db: Session = Depends(get_raw_db)
) -> GlobalStatsResponse:
    """
    Returns global platform statistics:
    - Organization count
    - User count
    - Case counts by status
    - Document count
    - Report version count
    - GCS bucket size (optional, may timeout)
    """
    try:
        org_count = db.query(func.count(Organization.id)).scalar() or 0
        user_count = db.query(func.count(User.id)).scalar() or 0
        document_count = db.query(func.count(Document.id)).scalar() or 0
        report_count = db.query(func.count(ReportVersion.id)).scalar() or 0
        case_counts = _get_case_counts_by_status(db)

        # GCS bucket size - may timeout on large buckets
        gcs_size = _get_bucket_size_gb_safe(timeout_seconds=5.0)

        logger.info(
            f"Global stats requested by superadmin: {org_count} orgs, {user_count} users"
        )

        return GlobalStatsResponse(
            org_count=org_count,
            user_count=user_count,
            case_counts=case_counts,
            document_count=document_count,
            report_count=report_count,
            gcs_bucket_size_gb=gcs_size,
        )

    except Exception as e:
        logger.error(f"Failed to get global stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global statistics.",
        )


@router.get(
    "/stats/{org_id}",
    response_model=OrgStatsResponse,
    summary="Get Organization Stats",
    description="Superadmin only: Get statistics for a specific organization.",
)
def get_org_stats(
    org_id: uuid.UUID,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_raw_db),
) -> OrgStatsResponse:
    """
    Returns organization-level statistics:
    - User count in org
    - Case counts by status
    - Document count
    - List of users (for dropdown navigation)
    """
    # Verify org exists
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    try:
        # Get counts scoped to org
        user_count = (
            db.query(func.count(User.id))
            .filter(User.organization_id == org_id)
            .scalar()
            or 0
        )
        document_count = (
            db.query(func.count(Document.id))
            .filter(Document.organization_id == org_id)
            .scalar()
            or 0
        )
        case_counts = _get_case_counts_by_status(db, org_id=org_id)

        # Get users for dropdown
        users = db.query(User).filter(User.organization_id == org_id).all()
        user_summaries = [
            UserSummary(
                id=u.id,
                email=u.email,
                first_name=u.first_name,
                last_name=u.last_name,
            )
            for u in users
        ]

        logger.info(f"Org stats requested for {org.name} ({org_id})")

        return OrgStatsResponse(
            org_id=str(org_id),
            org_name=org.name,
            user_count=user_count,
            case_counts=case_counts,
            document_count=document_count,
            users=user_summaries,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get org stats for {org_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve organization statistics.",
        )


@router.get(
    "/stats/{org_id}/users/{user_id}",
    response_model=UserStatsResponse,
    summary="Get User Stats",
    description="Superadmin only: Get statistics for a specific user.",
)
def get_user_stats(
    org_id: uuid.UUID,
    user_id: str,  # Firebase UID is a STRING, not UUID!
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_raw_db),
) -> UserStatsResponse:
    """
    Returns user-level statistics:
    - Total cases created
    - Cases created today
    - Cases created in last 7 days
    - Cases by status
    """
    # Verify user exists and belongs to the specified org
    user = (
        db.query(User)
        .filter(User.id == user_id, User.organization_id == org_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this organization",
        )

    try:
        # Get case counts
        case_counts = _get_case_counts_by_status(db, user_id=user_id)
        total_cases = sum(
            [
                case_counts.OPEN,
                case_counts.CLOSED,
                case_counts.ERROR,
                case_counts.GENERATING,
                case_counts.PROCESSING,
                case_counts.ARCHIVED,
            ]
        )

        # Cases today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cases_today = (
            db.query(func.count(Case.id))
            .filter(
                Case.creator_id == user_id,
                Case.created_at >= today_start,
                Case.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )

        # Cases last 7 days
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        cases_last_7_days = (
            db.query(func.count(Case.id))
            .filter(
                Case.creator_id == user_id,
                Case.created_at >= week_ago,
                Case.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )

        logger.info(f"User stats requested for {user.email} ({user_id})")

        return UserStatsResponse(
            user_id=user_id,
            user_email=user.email,
            total_cases=total_cases,
            cases_today=cases_today,
            cases_last_7_days=cases_last_7_days,
            cases_by_status=case_counts,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user stats for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics.",
        )
