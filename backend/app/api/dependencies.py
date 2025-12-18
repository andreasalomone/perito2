import contextlib
import logging
import os
from typing import Any, AsyncGenerator, Generator, Optional

import firebase_admin
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_raw_db
from app.models import User

# Configure structured logging
logger = logging.getLogger("app.auth")

security = HTTPBearer(auto_error=False)

# SQL constants to avoid duplication
SQL_SET_USER_UID = "SELECT set_config('app.current_user_uid', :uid, false)"
SQL_RESET_USER_UID = "RESET app.current_user_uid"
SQL_RESET_ORG_ID = "RESET app.current_org_id"
# NOTE: SQL_RESET_RLS_ALL removed - asyncpg requires separate statements


# -----------------------------------------------------------------------------
# 1. Firebase Initialization
# -----------------------------------------------------------------------------
def initialize_firebase() -> None:
    """
    Idempotent Firebase initialization.
    Handles both local development (SA file) and Cloud Run (ADC).
    """
    with contextlib.suppress(ValueError):
        firebase_admin.get_app()
        return  # Already initialized
    logger.info("🔥 Initializing Firebase Admin SDK...")

    # In Cloud Run, we mount the secret to /secrets/service-account.json
    cred_path = "/secrets/service-account.json"

    if os.path.exists(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info(f"✅ Firebase initialized with credentials from {cred_path}")
            return
        except Exception as e:
            logger.warning(
                f"⚠️ Failed to load Firebase credentials from {cred_path}: {e}"
            )
            logger.info("Falling back to Application Default Credentials (ADC).")

    # Fallback to ADC or GOOGLE_APPLICATION_CREDENTIALS env var
    try:
        firebase_admin.initialize_app()
        logger.info(
            "✅ Firebase initialized with Application Default Credentials (ADC)"
        )
    except Exception as e:
        logger.critical(f"❌ Failed to initialize Firebase: {e}")
        raise RuntimeError("Firebase initialization failed") from e


# Initialize on module load (safe because it's idempotent)
initialize_firebase()


# -----------------------------------------------------------------------------
# 2. Authentication Dependency
# -----------------------------------------------------------------------------
def get_current_user_token(
    creds: HTTPAuthorizationCredentials | None = Security(security),
) -> dict[str, Any]:
    """
    Validates the Firebase ID Token.
    Returns the decoded token dictionary.
    """
    # DEV BYPASS: Skip Firebase validation for local development
    if settings.RUN_LOCALLY and settings.SKIP_AUTH:
        if settings.DEV_USER_UID and settings.DEV_USER_EMAIL:
            logger.warning("⚠️ AUTH BYPASS: Using dev user for local testing")
            return {
                "uid": settings.DEV_USER_UID,
                "email": settings.DEV_USER_EMAIL,
            }
        else:
            logger.error("SKIP_AUTH=True but DEV_USER_UID/DEV_USER_EMAIL not set!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Dev auth bypass misconfigured",
            )

    # Normal auth flow requires credentials
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials
    try:
        # verify_id_token checks signature, expiration, and format
        decoded_token: dict[str, Any] = auth.verify_id_token(token, check_revoked=True)
        return decoded_token
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (auth.AuthError, ValueError) as e:
        # AuthError: base class for Firebase auth exceptions not caught above
        # ValueError: malformed token structure
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# -----------------------------------------------------------------------------
# 3. Secure Database Session (RLS)
# -----------------------------------------------------------------------------
from app.db.session import set_rls_variables


# -----------------------------------------------------------------------------
# 3. Secure Database Session (RLS)
# -----------------------------------------------------------------------------
def get_db(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db),
) -> Generator[Session, None, None]:
    """
    Secure Database Session Dependency.
    1. Gets the User's UID from Firebase Token.
    2. Finds their Organization in Postgres.
    3. SETS the 'app.current_org_id' session variable.
    4. Returns the secured session.
    """
    uid = current_user_token["uid"]
    email = current_user_token.get("email", "unknown")

    logger.info(f"get_db: Processing request for user {uid} ({email})")

    try:
        # 1. Set the User UID session variable FIRST
        # This allows the 'user_self_access' RLS policy to let us read our own record.
        # We use is_local=False to ensure it persists if we commit, but we MUST reset it.
        try:
            db.execute(
                text(SQL_SET_USER_UID),
                {"uid": uid},
            )
            logger.debug(f"get_db: Set app.current_user_uid to {uid}")
        except Exception as e:
            logger.error(
                f"get_db: Failed to set app.current_user_uid for {uid}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="Database session initialization failed"
            ) from e

        # 2. Now we can safely query the User table
        try:
            # OPTIMIZATION: Query only the organization_id to avoid loading heavy columns
            user_msg = db.execute(
                text("SELECT organization_id FROM users WHERE id = :uid"), {"uid": uid}
            ).fetchone()

            logger.debug(f"get_db: User query result for {uid}: {user_msg is not None}")
        except Exception as e:
            logger.error(f"get_db: Failed to query user {uid}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Failed to query user record"
            ) from e

        if not user_msg:
            # Phantom User Race Condition
            logger.warning(
                f"get_db: User {uid} ({email}) authenticated but not found in database."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account not initialized. Please complete registration first.",
            )

        org_id = str(user_msg.organization_id)
        logger.info(f"get_db: User {uid} belongs to organization {org_id}")

        # 3. Set the Full RLS Context (User + Org) using the shared helper
        # This uses is_local=False
        try:
            set_rls_variables(db, uid, org_id)
            logger.debug(f"get_db: Set app.current_org_id to {org_id}")
        except Exception as e:
            logger.error(
                f"get_db: Failed to set RLS variables for {uid}: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Database session initialization failed"
            ) from e

        logger.info(
            f"get_db: Successfully initialized session for user {uid} in org {org_id}"
        )

        # 4. Yield the session
        yield db

    finally:
        # 5. Cleanup is now handled centrally by SQLAlchemy pool listeners in database.py
        # This ensures consistency even if this dependency is bypassed or if transactions fail.
        pass


# -----------------------------------------------------------------------------
# 3b. Registration Database Session (Permissive)
# -----------------------------------------------------------------------------
def get_registration_db(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db),
) -> Generator[Session, None, None]:
    """
    Permissive Dependency for the /sync endpoint.
    Sets the User UID context (for RLS 'user_self_access') but DOES NOT require
    the user to exist in the User table yet. This allows first-time registration.
    """
    uid = current_user_token["uid"]

    try:
        # Use is_local=False for consistency and safety against commits
        db.execute(text(SQL_SET_USER_UID), {"uid": uid})
        yield db
    except Exception as e:
        logger.error(f"Failed to set app.current_user_uid for registration: {e}")
        raise HTTPException(
            status_code=500, detail="Database context initialization failed"
        ) from e
    finally:
        # Cleanup is now handled centrally by database.py pool listeners
        pass


# -----------------------------------------------------------------------------
# 3c. Async Database Session with RLS (for async endpoints)
# -----------------------------------------------------------------------------
from app.db.database import AsyncSessionLocal


async def get_async_db(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Async Database Session Dependency with proper RLS context.

    This is the safe alternative to creating AsyncSessionLocal inside endpoints.
    It properly:
    1. Sets RLS context before yielding
    2. Resets context on cleanup (even on error)
    3. Invalidates connection if reset fails

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(db: AsyncSession = Depends(get_async_db)):
            ...
    """
    uid = current_user_token["uid"]

    async with AsyncSessionLocal() as db:
        try:
            # 1. Get user's organization (one query to set context)
            result = await db.execute(
                text("SELECT organization_id FROM users WHERE id = :uid"), {"uid": uid}
            )
            user_row = result.fetchone()

            if not user_row:
                logger.warning(f"get_async_db: User {uid} not found in database.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account not initialized.",
                )

            org_id = str(user_row.organization_id)

            # 2. Set RLS variables (is_local=false to persist across statements)
            await db.execute(
                text(SQL_SET_USER_UID),
                {"uid": uid},
            )
            await db.execute(
                text("SELECT set_config('app.current_org_id', :oid, false)"),
                {"oid": org_id},
            )
            logger.debug(
                f"get_async_db: Set RLS context for user {uid} in org {org_id}"
            )

            yield db

        finally:
            # 3. Cleanup is now handled centrally by database.py pool listeners
            pass


# -----------------------------------------------------------------------------
# 4. Superadmin Dependency
# -----------------------------------------------------------------------------
def get_superadmin_user(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db),  # Use raw DB, skip RLS for superadmins
) -> Optional[User]:
    """
    Dependency for superadmin-only endpoints.
    Checks if the current user's email is in the superadmin list.

    Note: Uses raw DB connection without RLS to allow superadmins
    to operate without organization membership.
    """
    email = current_user_token.get("email")

    if not email:
        raise HTTPException(status_code=403, detail="Email not found in token")

    if email not in settings.SUPERADMIN_EMAIL_LIST:
        logger.warning(f"Unauthorized superadmin access attempt by {email}")
        raise HTTPException(status_code=403, detail="Superadmin access required")

    # Superadmins don't need to have a User record or belong to an organization
    # They can operate independently
    uid = current_user_token["uid"]
    return db.query(User).filter(User.id == uid).first()
