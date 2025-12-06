import logging
from typing import Any, Dict, Optional

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_token, get_registration_db
from app.models import AllowedEmail, User
from app.schemas.enums import UserRole

# Configure Structured Logging
logger = logging.getLogger("app.auth.sync")

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. Pydantic Models (Strict API Contracts)
# -----------------------------------------------------------------------------
class UserRead(BaseModel):
    """
    Public-facing user profile.
    Excludes sensitive internal fields if any.
    """
    id: str
    email: EmailStr
    organization_id: UUID  # Changed to UUID to match ORM model
    role: UserRole

    class Config:
        from_attributes = True # Replaces 'orm_mode = True' in Pydantic v2

# -----------------------------------------------------------------------------
# 2. The Refactored Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/sync",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Sync Firebase User",
    description="Idempotently syncs a Firebase user to the internal Postgres database."
)
def sync_user(
    token: Dict[str, Any] = Depends(get_current_user_token),
    db: Session = Depends(get_registration_db)  # Permissive: doesn't require User to exist
) -> User:
    """
    Synchronizes the authenticated Firebase user with the local database.
    
    Flow:
    1. Check if user exists (Fast Path).
    2. If not, validate against AllowedEmail whitelist.
    3. create user safely (handling concurrency).
    """
    # 1. Input Sanitization
    uid: str | None = token.get("uid")
    email: str | None = token.get("email")
    # FIX: Normalize email to lower case immediately to prevent case sensitivity issues
    if email:
        email = email.lower()

    if not uid or not email:
        logger.warning("Sync attempted with invalid token claims.", extra={"token_keys": token.keys()})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Token missing required claims (uid, email)."
        )

    # 2. Fast Path: User Already Exists
    # Use scalar queries for modern SQLAlchemy 2.0 style
    stmt = select(User).where(User.id == uid)
    db_user = db.scalar(stmt)

    if db_user:
        return db_user

    # 3. Slow Path: New User Registration
    logger.info(f"New user registration attempt: {email}")

    # Check Whitelist
    invite_stmt = select(AllowedEmail).where(AllowedEmail.email == email)
    allowed_email = db.scalar(invite_stmt)

    if not allowed_email:
        logger.warning(f"Registration rejected: Email not whitelisted: {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Please contact your administrator for an invite."
        )

    # 4. Atomic Creation
    try:
        new_user = User(
            id=uid,
            email=email,
            organization_id=allowed_email.organization_id,
            role=UserRole(allowed_email.role) if allowed_email.role else UserRole.MEMBER
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"User created successfully: {uid} (Org: {allowed_email.organization_id})")
        return new_user

    except IntegrityError:
        # 5. Race Condition Handling
        # If two requests hit this block simultaneously, the database unique constraint
        # will fail the second one. We catch this, rollback, and return the existing user.
        db.rollback()
        logger.warning(f"Race condition detected for user {uid}. Recovering...")
        
        existing_user = db.scalar(select(User).where(User.id == uid))
        if existing_user:
            return existing_user
        
        # If we still can't find it, something is truly broken
        logger.error(f"IntegrityError raised but user {uid} not found.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while synchronizing user profile."
        )
        
    except Exception as e:
        # Catch-all for unexpected errors (Network, DB connection lost, etc.)
        logger.error(f"Unexpected error syncing user {uid}: {e}", exc_info=True)
        # NEVER return 'str(e)' to the client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
