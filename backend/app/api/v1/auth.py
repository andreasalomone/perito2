import logging
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_raw_db
from app.api.dependencies import get_current_user_token, get_registration_db
from app.models import AllowedEmail, Organization, User
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
    Includes profile completion status for onboarding flow.
    """
    id: str
    email: EmailStr
    organization_id: UUID
    role: UserRole
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_profile_complete: bool
    organization_name: str
    
    # Audit fields required by frontend
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class CheckStatusRequest(BaseModel):
    """Request for pre-auth email status check."""
    email: EmailStr


class CheckStatusResponse(BaseModel):
    """Response for pre-auth email status check."""
    status: Literal["registered", "invited", "denied"]

# -----------------------------------------------------------------------------
# 2. Pre-Auth Email Check (Public Endpoint)
# -----------------------------------------------------------------------------
@router.post(
    "/check-status",
    response_model=CheckStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check Email Status",
    description="Public endpoint to check if an email is registered, invited, or denied."
)
def check_user_status(
    request: CheckStatusRequest,
    db: Session = Depends(get_raw_db)
) -> CheckStatusResponse:
    """Check email status before authentication."""
    email = request.email.lower().strip()
    
    # 1. Check if registered
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return CheckStatusResponse(status="registered")
    
    # 2. Check if invited (whitelisted)
    invite = db.scalar(select(AllowedEmail).where(AllowedEmail.email == email))
    if invite:
        return CheckStatusResponse(status="invited")
    
    # 3. Not allowed
    return CheckStatusResponse(status="denied")


# -----------------------------------------------------------------------------
# 3. The Refactored Sync Endpoint
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
    # Use scalar queries for modern SQLAlchemy 2.0 style
    # FIX: Eager load organization to prevent N+1 on property access
    from sqlalchemy.orm import joinedload
    stmt = select(User).options(joinedload(User.organization)).where(User.id == uid)
    db_user = db.scalar(stmt)

    if db_user:
        # Update last_login timestamp for returning users
        db_user.last_login = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_user)
        return db_user

    # 3. Slow Path: New User Registration
    logger.info(f"New user registration attempt: {email}")

    # Check Whitelist
    invite_stmt = select(AllowedEmail).where(AllowedEmail.email == email)
    allowed_email = db.scalar(invite_stmt)

    # --- 3b. Superadmin Bootstrap (Break Glass) ---
    # If the DB was wiped, normal users can't login because the whitelist is empty.
    # We allow Superadmins (defined in env vars) to auto-provision themselves.
    if not allowed_email and email in settings.SUPERADMIN_EMAIL_LIST:
        logger.warning(f"Superadmin detected in empty system: {email}. Auto-provisioning...")
        
        # 1. Ensure an Organization exists
        org_stmt = select(Organization).limit(1)
        existing_org = db.scalar(org_stmt)
        
        if not existing_org:
            logger.info("No organizations found. Creating default 'System Admin Org'.")
            existing_org = Organization(name="System Admin Org")
            db.add(existing_org)
            db.flush() # Flush to get ID
            
        # 2. Add to Whitelist
        allowed_email = AllowedEmail(
            organization_id=existing_org.id,
            email=email,
            role=UserRole.ADMIN
        )
        db.add(allowed_email)
        db.commit()
        db.refresh(allowed_email)
        logger.info(f"Superadmin auto-whitelisted: {email}")

    # --- End Bootstrap ---
    
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
