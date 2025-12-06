import logging
import uuid
from typing import List
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.dependencies import get_superadmin_user
from app.models import User, Organization, AllowedEmail, Case
from app.schemas.enums import UserRole, CaseStatus
from datetime import datetime, timedelta, timezone

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

# ============= Endpoints =============

@router.get(
    "/organizations",
    response_model=List[OrganizationResponse],
    summary="List Organizations",
    description="Retrieve a list of all registered organizations."
)
def list_organizations(
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> List[Organization]:
    """
    Superadmin only: List all organizations.
    """
    # Modern SQLAlchemy 2.0 syntax
    stmt = select(Organization).order_by(Organization.name)
    return db.scalars(stmt).all()

@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization"
)
def create_organization(
    request: OrganizationBase,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
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
            detail="An organization with this name likely already exists."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )

@router.get(
    "/organizations/{org_id}/invites",
    response_model=List[AllowedEmailResponse],
    summary="List Invites"
)
def list_org_invites(
    org_id: uuid.UUID, # FastAPI automatically validates UUID format here
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> List[AllowedEmail]:
    """
    Superadmin only: List all whitelisted emails for an organization.
    """
    # Verify org exists first
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    stmt = select(AllowedEmail).where(AllowedEmail.organization_id == org_id)
    return db.scalars(stmt).all()

@router.post(
    "/organizations/{org_id}/users/invite",
    response_model=GenericMessage,
    status_code=status.HTTP_201_CREATED,
    summary="Invite User"
)
def invite_user_to_org(
    org_id: uuid.UUID,
    request: InviteUserRequest,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> GenericMessage:
    """
    Superadmin only: Whitelist an email for a specific organization.
    """
    # 1. Validation: Organization
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # 2. Validation: Already Whitelisted?
    # Uses 'select' with 'limit(1)' implicitly via scalar_one_or_none logic usually, 
    # but scalar() works efficiently here.
    invite_stmt = select(AllowedEmail).where(AllowedEmail.email == request.email)
    if db.scalar(invite_stmt):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already whitelisted."
        )
    
    # 3. Validation: User Already Exists?
    user_stmt = select(User).where(User.email == request.email)
    if db.scalar(user_stmt):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already registered in the system."
        )
    
    # 4. Action: Create Invite
    try:
        new_invite = AllowedEmail(
            organization_id=org_id,
            email=request.email,
            role=request.role.value
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
            detail="Failed to process invite."
        )

@router.delete(
    "/invites/{invite_id}",
    response_model=GenericMessage,
    summary="Revoke Invite"
)
def delete_invite(
    invite_id: uuid.UUID,
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> GenericMessage:
    """
    Superadmin only: Remove a whitelisted email.
    """
    invite = db.get(AllowedEmail, invite_id)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found"
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
            detail="Failed to delete invite."
        )

@router.post(
    "/storage/cleanup",
    response_model=dict,
    summary="Cleanup Orphaned GCS Files"
)
def cleanup_orphaned_storage(
    superadmin: User = Depends(get_superadmin_user),
) -> dict:
    """
    Superadmin only: Deletes orphaned files from GCS uploads/ directory.
    
    This endpoint implements metadata-aware cleanup that the GCS Lifecycle
    Policy cannot provide. It safely removes files older than 24 hours that
    were uploaded but never successfully registered in the database.
    
    **How it works:**
    1. Lists all blobs in the `uploads/` prefix
    2. Checks blob age (must be > 24 hours old)
    3. Checks blob metadata for `status=finalized` tag
    4. Deletes only files that are old AND not finalized
    
    **Security:** This endpoint should be called by Cloud Scheduler with 
    OIDC authentication or manually by superadmin users.
    
    **Idempotent:** Safe to run multiple times without side effects.
    """
    from datetime import datetime, timedelta, timezone
    from app.core.config import settings
    from app.services import gcs_service
    
    try:
        client = gcs_service.get_storage_client()
        bucket = client.bucket(settings.STORAGE_BUCKET_NAME)
        
        # List all blobs in uploads/
        blobs = bucket.list_blobs(prefix="uploads/")
        
        deleted_count = 0
        skipped_count = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        for blob in blobs:
            # 1. Age Check: Only process files older than 24 hours
            if blob.time_created < cutoff_time:
                # 2. Metadata Check: blob.metadata is None if no metadata set
                metadata = blob.metadata or {}
                
                # 3. Decision: Delete only if NOT finalized
                if metadata.get("status") != "finalized":
                    logger.info(f"Deleting orphaned blob: {blob.name} (age: {blob.time_created})")
                    blob.delete()
                    deleted_count += 1
                else:
                    # File is old but has finalized tag - keep it
                    skipped_count += 1
            else:
                # File is too new to delete
                skipped_count += 1
        
        logger.info(f"Storage cleanup completed: {deleted_count} deleted, {skipped_count} preserved")
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "skipped_count": skipped_count,
            "cutoff_time": cutoff_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Storage cleanup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup operation failed: {str(e)}"
        )

@router.post(
    "/rescue-zombies",
    response_model=dict,
    summary="Rescue Stuck Cases"
)
def rescue_stuck_cases(
    superadmin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Superadmin only: Reset cases stuck in 'GENERATING' state for > 30 minutes.
    
    These "zombie" cases occur if a worker crashes (OOM/Timeout) before updating the status.
    This endpoint finds them and marks them as ERROR so users can retry.
    """
    try:
        # Define cutoff time (30 minutes ago)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        # Find stuck cases
        # status == GENERATING AND updated_at < cutoff
        stmt = select(Case).where(
            Case.status == CaseStatus.GENERATING,
            Case.updated_at < cutoff_time
        )
        stuck_cases = db.scalars(stmt).all()
        
        rescued_count = 0
        for case in stuck_cases:
            logger.warning(f"Rescuing zombie case {case.id} (stuck since {case.updated_at})")
            case.status = CaseStatus.ERROR
            rescued_count += 1
            
        db.commit()
        
        logger.info(f"Zombie rescue completed: {rescued_count} cases reset to ERROR")
        
        return {
            "status": "success",
            "rescued_count": rescued_count,
            "cutoff_time": cutoff_time.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Zombie rescue failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rescue operation failed: {str(e)}"
        )
