from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from deps import get_current_user_token
from core.models import User, Organization

router = APIRouter()

@router.post("/sync")
def sync_user(
    current_user_token: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """
    Syncs the Firebase user with the local database.
    If the user doesn't exist, creates a new User and a default Organization.
    """
    uid = current_user_token['uid']
    email = current_user_token.get('email')
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Check if user exists
    # Note: RLS might block this if we don't handle it. 
    # But deps.get_db sets app.current_user_uid, so we should be able to read our own record if RLS is on for users.
    db_user = db.query(User).filter(User.id == uid).first()
    
    if not db_user:
        # Create new Organization (Default to "My Organization")
        new_org = Organization(name="My Organization")
        db.add(new_org)
        db.flush() # Flush to get the ID

        # Create new User
        db_user = User(
            id=uid,
            email=email,
            organization_id=new_org.id,
            role="admin" # First user is Admin of their own Org
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
    return {
        "id": db_user.id,
        "email": db_user.email,
        "organization_id": db_user.organization_id,
        "role": db_user.role
    }
