import logging
import os
from typing import Any, Generator, Optional

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


# -----------------------------------------------------------------------------
# 1. Firebase Initialization
# -----------------------------------------------------------------------------
def initialize_firebase() -> None:
    """
    Idempotent Firebase initialization.
    Handles both local development (SA file) and Cloud Run (ADC).
    """
    try:
        firebase_admin.get_app()
        return  # Already initialized
    except ValueError:
        pass  # Not initialized yet

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
        )
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (auth.AuthError, ValueError) as e:
        # AuthError: base class for Firebase auth exceptions not caught above
        # ValueError: malformed token structure
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


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

    # Track if we have dirtied the connection
    connection_dirtied = False

    try:
        # 1. Set the User UID session variable FIRST
        # This allows the 'user_self_access' RLS policy to let us read our own record.
        # We use is_local=False to ensure it persists if we commit, but we MUST reset it.
        try:
            db.execute(
                text("SELECT set_config('app.current_user_uid', :uid, false)"),
                {"uid": uid},
            )
            connection_dirtied = True
            logger.debug(f"get_db: Set app.current_user_uid to {uid}")
        except Exception as e:
            logger.error(
                f"get_db: Failed to set app.current_user_uid for {uid}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="Database session initialization failed"
            )

        # 2. Now we can safely query the User table
        try:
            # OPTIMIZATION: Query only the organization_id to avoid loading heavy columns
            user_msg = db.execute(
                text("SELECT organization_id FROM users WHERE id = :uid"), {"uid": uid}
            ).fetchone()

            logger.debug(f"get_db: User query result for {uid}: {user_msg is not None}")
        except Exception as e:
            logger.error(f"get_db: Failed to query user {uid}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to query user record")

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
            )

        logger.info(
            f"get_db: Successfully initialized session for user {uid} in org {org_id}"
        )

        # 4. Yield the session
        yield db

    finally:
        # 5. CRITICAL: RESET variables before returning connection to pool
        if connection_dirtied:
            try:
                db.execute(
                    text("RESET app.current_user_uid; RESET app.current_org_id;")
                )
            except Exception as e:
                logger.warning(
                    f"Initial RESET RLS failed in get_db (likely aborted transaction): {e}. Attempting rollback."
                )
                try:
                    # If the transaction is aborted, we must rollback before we can run RESET
                    db.rollback()
                    db.execute(
                        text("RESET app.current_user_uid; RESET app.current_org_id;")
                    )
                    logger.info(
                        "Successfully reset RLS context in get_db after rollback."
                    )
                except Exception as e2:
                    logger.critical(
                        f"FAILED TO RESET RLS CONTEXT in get_db after rollback: {e2}"
                    )
                    # Invalidate connection to prevent data leak
                    db.invalidate()


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
    connection_dirtied = False

    try:
        # Use is_local=False for consistency and safety against commits
        db.execute(
            text("SELECT set_config('app.current_user_uid', :uid, false)"), {"uid": uid}
        )
        connection_dirtied = True
        yield db
    except Exception as e:
        logger.error(f"Failed to set app.current_user_uid for registration: {e}")
        raise HTTPException(
            status_code=500, detail="Database context initialization failed"
        )
    finally:
        if connection_dirtied:
            try:
                db.execute(text("RESET app.current_user_uid;"))
            except Exception as e:
                logger.warning(
                    f"Initial RESET RLS failed in get_registration_db (likely aborted transaction): {e}. Attempting rollback."
                )
                try:
                    db.rollback()
                    db.execute(text("RESET app.current_user_uid;"))
                    logger.info(
                        "Successfully reset RLS context in get_registration_db after rollback."
                    )
                except Exception as e2:
                    logger.critical(
                        f"FAILED TO RESET RLS CONTEXT in get_registration_db after rollback: {e2}"
                    )
                    db.invalidate()


# -----------------------------------------------------------------------------
# 3c. Async Database Session with RLS (for async endpoints)
# -----------------------------------------------------------------------------
from app.db.database import AsyncSessionLocal


async def get_async_db(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
) -> AsyncSession:
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
    """
    uid = current_user_token["uid"]
    connection_dirtied = False

    async with AsyncSessionLocal() as db:
        try:
            # 1. Get user's organization (one query to set context)
            result = await db.execute(
                text("SELECT organization_id FROM users WHERE id = :uid"),
                {"uid": uid}
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
                text("SELECT set_config('app.current_user_uid', :uid, false)"),
                {"uid": uid}
            )
            await db.execute(
                text("SELECT set_config('app.current_org_id', :oid, false)"),
                {"oid": org_id}
            )
            connection_dirtied = True

            logger.debug(f"get_async_db: Set RLS context for user {uid} in org {org_id}")

            yield db

        finally:
            # 3. CRITICAL: Reset RLS context before returning to pool
            if connection_dirtied:
                try:
                    await db.execute(
                        text("RESET app.current_user_uid; RESET app.current_org_id;")
                    )
                except Exception as e:
                    logger.warning(f"get_async_db: Initial RESET failed: {e}. Attempting rollback.")
                    try:
                        await db.rollback()
                        await db.execute(
                            text("RESET app.current_user_uid; RESET app.current_org_id;")
                        )
                    except Exception as e2:
                        logger.critical(f"get_async_db: FAILED TO RESET RLS after rollback: {e2}")
                        # Invalidate connection to prevent potential data leak
                        await db.invalidate()


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
    user_record = db.query(User).filter(User.id == uid).first()

    # Return the user if exists, None if not (superadmin doesn't need User record)
    return user_record
