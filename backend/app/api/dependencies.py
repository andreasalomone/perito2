import logging
import os
from typing import Generator, Optional, Any

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db as get_raw_db
from app.models import User
from app.core.config import settings

# Configure structured logging
logger = logging.getLogger("app.auth")

security = HTTPBearer()

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
            logger.warning(f"⚠️ Failed to load Firebase credentials from {cred_path}: {e}")
            logger.info("Falling back to Application Default Credentials (ADC).")

    # Fallback to ADC or GOOGLE_APPLICATION_CREDENTIALS env var
    try:
        firebase_admin.initialize_app()
        logger.info("✅ Firebase initialized with Application Default Credentials (ADC)")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize Firebase: {e}")
        raise RuntimeError("Firebase initialization failed") from e

# Initialize on module load (safe because it's idempotent)
initialize_firebase()

# -----------------------------------------------------------------------------
# 2. Authentication Dependency
# -----------------------------------------------------------------------------
def get_current_user_token(creds: HTTPAuthorizationCredentials = Security(security)) -> dict[str, Any]:
    """
    Validates the Firebase ID Token.
    Returns the decoded token dictionary.
    """
    token = creds.credentials
    try:
        # verify_id_token checks signature, expiration, and format
        decoded_token = auth.verify_id_token(token, check_revoked=True)
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
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# -----------------------------------------------------------------------------
# 3. Secure Database Session (RLS)
# -----------------------------------------------------------------------------
def get_db(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db)
) -> Generator[Session, None, None]:
    """
    Secure Database Session Dependency.
    1. Gets the User's UID from Firebase Token.
    2. Finds their Organization in Postgres.
    3. SETS the 'app.current_org_id' session variable.
    4. Returns the secured session.
    """
    uid = current_user_token['uid']
    
    # 1. Set the User UID session variable FIRST
    # This allows the 'user_self_access' RLS policy to let us read our own record.
    try:
        db.execute(
            text("SELECT set_config('app.current_user_uid', :uid, true)"), 
            {"uid": uid}
        )
    except Exception as e:
        logger.error(f"Failed to set app.current_user_uid: {e}")
        raise HTTPException(status_code=500, detail="Database session initialization failed")
    
    # 2. Now we can safely query the User table
    user_record = db.query(User).filter(User.id == uid).first()
    
    if not user_record:
        # Phantom User Race Condition: User authenticated in Firebase but not yet synced to DB
        logger.warning(f"User {uid} authenticated but not found in database.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account not initialized. Please complete registration first."
        )

    org_id = str(user_record.organization_id)
    
    # 3. Set the Organization ID session variable
    # If RLS is on, Postgres now filters everything automatically.
    try:
        db.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"), 
            {"org_id": org_id}
        )
    except Exception as e:
        logger.error(f"Failed to set app.current_org_id: {e}")
        raise HTTPException(status_code=500, detail="Database session initialization failed")
    
    yield db

# -----------------------------------------------------------------------------
# 4. Superadmin Dependency
# -----------------------------------------------------------------------------
def get_superadmin_user(
    current_user_token: dict[str, Any] = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db)  # Use raw DB, skip RLS for superadmins
) -> Optional[User]:
    """
    Dependency for superadmin-only endpoints.
    Checks if the current user's email is in the superadmin list.
    
    Note: Uses raw DB connection without RLS to allow superadmins
    to operate without organization membership.
    """
    email = current_user_token.get('email')
    
    if not email:
        raise HTTPException(status_code=403, detail="Email not found in token")
    
    if email not in settings.SUPERADMIN_EMAIL_LIST:
        logger.warning(f"Unauthorized superadmin access attempt by {email}")
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    # Superadmins don't need to have a User record or belong to an organization
    # They can operate independently
    uid = current_user_token['uid']
    user_record = db.query(User).filter(User.id == uid).first()
    
    # Return the user if exists, None if not (superadmin doesn't need User record)
    return user_record
