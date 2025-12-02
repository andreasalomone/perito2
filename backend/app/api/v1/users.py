from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.db.database import get_db
from app.api.dependencies import get_current_user_token
from app.models import User, Organization, AllowedEmail

router = APIRouter()

class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "member"

@router.post("/invite")
def invite_user(
    request: InviteUserRequest,
    current_user_token: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """
    Admins can whitelist an email for their Organization.
    """
    uid = current_user_token['uid']
    
    # 1. Get Current Admin User
    admin_user = db.query(User).filter(User.id == uid).first()
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin not found")
        
    if admin_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can invite users")
    
    # 2. Check if email is already allowed
    existing_invite = db.query(AllowedEmail).filter(AllowedEmail.email == request.email).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="Email is already invited")

    # 3. Check if user already exists (optional, but good UX)
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already registered")

    # 4. Create Invite
    new_invite = AllowedEmail(
        organization_id=admin_user.organization_id,
        email=request.email,
        role=request.role
    )
    db.add(new_invite)
    db.commit()
    
    return {"message": f"User {request.email} invited successfully"}
