import logging
from typing import Annotated, Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_token
from app.api.dependencies import get_db
from app.models import AllowedEmail, User
from app.schemas.enums import UserRole

# Configure Structured Logging
logger = logging.getLogger("app.api.invites")

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. Strict Types & Enums
# -----------------------------------------------------------------------------

class InviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Enforces lowercase for consistent email comparisons."""
        return v.lower().strip()

class GenericResponse(BaseModel):
    message: str


class ProfileUpdateRequest(BaseModel):
    """Request body for updating user profile."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class UserProfileResponse(BaseModel):
    """Response for profile operations."""
    id: str
    email: EmailStr
    organization_id: UUID
    role: UserRole
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_profile_complete: bool
    organization_name: str
    
    # Audit fields required by frontend
    created_at: Any  # Allowing Any for simplicity, or we can import datetime
    last_login: Optional[Any] = None

    class Config:
        from_attributes = True

# -----------------------------------------------------------------------------
# 2. Endpoint Logic
# -----------------------------------------------------------------------------
@router.post(
    "/invite",
    response_model=GenericResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite User to Organization",
    description="Whitelists an email address for registration within the admin's organization."
)
def invite_user(
    request: InviteUserRequest,
    token: Annotated[Dict[str, Any], Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)]
) -> GenericResponse:
    
    uid = token.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authentication token."
        )

    # 1. Validate Admin Authority
    # Use scalar() for modern SQLAlchemy 2.0 syntax
    admin_user = db.scalar(select(User).where(User.id == uid))
    
    if not admin_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin profile not found.")
        
    if admin_user.role != UserRole.ADMIN.value:
        logger.warning(f"Unauthorized invite attempt by user {uid}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Insufficient permissions."
        )
    
    # 2. Check: User Already Registered?
    # We check this first to fail fast.
    existing_user = db.scalar(select(User).where(User.email == request.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="User is already registered in the system."
        )

    # 3. Check: Invite Already Exists?
    existing_invite = db.scalar(select(AllowedEmail).where(AllowedEmail.email == request.email))
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Email {request.email} is already invited."
        )

    # 4. Atomic Creation
    try:
        new_invite = AllowedEmail(
            organization_id=admin_user.organization_id,
            email=request.email,
            role=request.role.value
        )
        db.add(new_invite)
        db.commit()
        
        logger.info(f"Invite created: {request.email} for Org {admin_user.organization_id} by {uid}")
        
        return GenericResponse(message=f"User {request.email} invited successfully")

    except IntegrityError:
        db.rollback()
        # Catch race condition where duplicate was inserted between check and commit
        logger.warning(f"Race condition detected on invite for {request.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already invited."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Database error inviting user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )


# -----------------------------------------------------------------------------
# 3. Profile Update Endpoint
# -----------------------------------------------------------------------------
@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
    description="Update current user's first name and last name."
)
def update_my_profile(
    request: ProfileUpdateRequest,
    token: Annotated[Dict[str, Any], Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Allows a user to update their own profile (first_name, last_name).
    This is required during the onboarding flow.
    """
    uid = token.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )
    
    from sqlalchemy.orm import joinedload
    user = db.scalar(select(User).options(joinedload(User.organization)).where(User.id == uid))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    user.first_name = request.first_name
    user.last_name = request.last_name
    db.commit()
    
    # RE-APPLY RLS CONTEXT (Fix for QueuePool connection swap after commit)
    from sqlalchemy import text
    try:
        db.execute(
            text("SELECT set_config('app.current_org_id', :oid, false)"), 
            {"oid": str(user.organization_id)}
        )
    except Exception as e:
        logger.warning(f"Failed to re-apply RLS context before refresh: {e}")
    
    db.refresh(user)
    
    logger.info(f"Profile updated for user: {uid}")
    return user
