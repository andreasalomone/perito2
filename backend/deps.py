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

def get_current_user(creds: HTTPAuthorizationCredentials = Security(security)):
    """
    Validates the Bearer Token (JWT) sent by the frontend.
    Returns the user dict if valid, or raises 401.
    """
    token = creds.credentials
    try:
        # Verify the ID token while checking if the token is revoked
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return decoded_token
        # Returns dict like: {'uid': 'abc...', 'email': 'user@example.com', ...}
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token revoked. Please login again.")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
