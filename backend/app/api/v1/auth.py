from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.dependencies import get_current_user_token
from app.models import User, Organization, AllowedEmail

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
        # Invite-Only: Check if email is whitelisted
        allowed_email = db.query(AllowedEmail).filter(AllowedEmail.email == email).first()
        
        if not allowed_email:
            raise HTTPException(status_code=403, detail="User not registered. Please contact your administrator.")
            
        # Create new User from Invite
        try:
            db_user = User(
                id=uid,
                email=email,
                organization_id=allowed_email.organization_id,
                role=allowed_email.role
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
            # Optional: Delete invite after use? 
            # Or keep it as a record? Let's keep it for now or maybe delete to keep table clean.
            # Let's keep it simple and just create the user.
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
        
    return {
        "id": db_user.id,
        "email": db_user.email,
        "organization_id": db_user.organization_id,
        "role": db_user.role
    }
