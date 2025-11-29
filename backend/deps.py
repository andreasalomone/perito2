import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Initialize Firebase Admin once
# On Cloud Run, it auto-discovers credentials from the environment.
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

security = HTTPBearer()

from database import get_db
from sqlalchemy.orm import Session
from core.models import User

def get_current_user(
    creds: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    """
    Validates the Bearer Token (JWT) sent by the frontend.
    Returns the user dict if valid, or raises 401.
    Also fetches the DB user to get the organization_id.
    """
    token = creds.credentials
    try:
        # Verify the ID token while checking if the token is revoked
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        
        # Fetch DB User
        db_user = db.query(User).filter(User.id == decoded_token['uid']).first()
        if db_user:
            decoded_token['organization_id'] = db_user.organization_id
            decoded_token['role'] = db_user.role
        else:
            # If user not in DB yet (e.g. first login before sync), 
            # we might want to allow them to proceed to sync endpoint,
            # but block other endpoints.
            # For now, we just don't add org_id.
            pass

        return decoded_token
        # Returns dict like: {'uid': 'abc...', 'email': 'user@example.com', 'organization_id': '...', ...}
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token revoked. Please login again.")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
