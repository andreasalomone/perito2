import logging
from enum import Enum
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_token
from app.db.database import get_db
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

