import firebase_admin
from firebase_admin import auth
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db as get_raw_db
from app.models import User

# Initialize Firebase (Keep existing code)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

security = HTTPBearer()

def get_current_user_token(creds: HTTPAuthorizationCredentials = Security(security)):
    """Validates Firebase Token"""
    token = creds.credentials
    try:
        return auth.verify_id_token(token, check_revoked=True)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_db(
    current_user_token: dict = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db)
):
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
    # FIX: Use bind parameters (:uid) instead of f-strings to prevent SQL injection
    db.execute(
        text("SELECT set_config('app.current_user_uid', :uid, false)"), 
        {"uid": uid}
    )
    
    # 2. Now we can safely query the User table
    user_record = db.query(User).filter(User.id == uid).first()
    
    if not user_record:
        # FIX: Phantom User Race Condition
        # User not synced yet - this is a critical error for protected endpoints
        # Don't yield a session without org context as it causes "Missing Organization Context" 500 errors
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="User account not initialized. Please complete registration first."
        )

    org_id = str(user_record.organization_id)
    
    # THE SECURITY MAGIC:
    # Set the session variable. If RLS is on, Postgres now filters everything automatically.
    # FIX: Use bind parameters (:org_id)
    db.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"), 
        {"org_id": org_id}
    )
    
    yield db

def get_superadmin_user(
    current_user_token: dict = Depends(get_current_user_token),
    db: Session = Depends(get_raw_db)  # Use raw DB, skip RLS for superadmins
):
    """
    Dependency for superadmin-only endpoints.
    Checks if the current user's email is in the superadmin list.
    
    Note: Uses raw DB connection without RLS to allow superadmins
    to operate without organization membership.
    """
    from app.core.config import settings
    
    email = current_user_token.get('email')
    
    if not email:
        raise HTTPException(status_code=403, detail="Email not found in token")
    
    if email not in settings.SUPERADMIN_EMAIL_LIST:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    # Superadmins don't need to have a User record or belong to an organization
    # They can operate independently
    uid = current_user_token['uid']
    user_record = db.query(User).filter(User.id == uid).first()
    
    # Return the user if exists, None if not (superadmin doesn't need User record)
    return user_record
