from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from enum import Enum
from app.db.database import get_db
from app.api.dependencies import get_superadmin_user
from app.models import User, Organization, AllowedEmail
import uuid

router = APIRouter()

# ============= Enums =============

class UserRole(str, Enum):
    """Valid user roles"""
    ADMIN = "admin"
    MEMBER = "member"

# ============= Request/Response Models =============

class CreateOrganizationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, strip_whitespace=True)

class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: str

class InviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER

class AllowedEmailResponse(BaseModel):
    id: str
    email: str
    role: str
    organization_id: str
    created_at: str

# ============= Endpoints =============

@router.get("/organizations")
def list_organizations(
    superadmin: Optional[User] = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> List[OrganizationResponse]:
    """
    Superadmin only: List all organizations.
    """
    orgs = db.query(Organization).all()
    
    return [
        OrganizationResponse(
            id=str(org.id),
            name=org.name,
            created_at=org.created_at.isoformat()
        )
        for org in orgs
    ]

@router.post("/organizations")
def create_organization(
    request: CreateOrganizationRequest,
    superadmin: Optional[User] = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> OrganizationResponse:
    """
    Superadmin only: Create a new organization.
    """
    try:
        new_org = Organization(name=request.name)
        db.add(new_org)
        db.commit()
        db.refresh(new_org)
        
        return OrganizationResponse(
            id=str(new_org.id),
            name=new_org.name,
            created_at=new_org.created_at.isoformat()
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")

@router.get("/organizations/{org_id}/invites")
def list_org_invites(
    org_id: str,
    superadmin: Optional[User] = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> List[AllowedEmailResponse]:
    """
    Superadmin only: List all whitelisted emails for an organization.
    """
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format")
    
    # Verify org exists
    org = db.query(Organization).filter(Organization.id == org_uuid).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    invites = db.query(AllowedEmail).filter(AllowedEmail.organization_id == org_uuid).all()
    
    return [
        AllowedEmailResponse(
            id=str(invite.id),
            email=invite.email,
            role=invite.role,
            organization_id=str(invite.organization_id),
            created_at=invite.created_at.isoformat()
        )
        for invite in invites
    ]

@router.post("/organizations/{org_id}/users/invite")
def invite_user_to_org(
    org_id: str,
    request: InviteUserRequest,
    superadmin: Optional[User] = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Superadmin only: Whitelist an email for a specific organization.
    """
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format")
    
    # Verify org exists
    org = db.query(Organization).filter(Organization.id == org_uuid).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check if email is already whitelisted
    existing_invite = db.query(AllowedEmail).filter(AllowedEmail.email == request.email).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="Email is already whitelisted")
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in the system")
    
    # Create invite
    try:
        new_invite = AllowedEmail(
            organization_id=org_uuid,
            email=request.email,
            role=request.role.value  # Get enum value
        )
        db.add(new_invite)
        db.commit()
        
        return {"message": f"User {request.email} invited to {org.name}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to invite user: {str(e)}")

@router.delete("/invites/{invite_id}")
def delete_invite(
    invite_id: str,
    superadmin: Optional[User] = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Superadmin only: Remove a whitelisted email.
    """
    try:
        invite_uuid = uuid.UUID(invite_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invite ID format")
    
    invite = db.query(AllowedEmail).filter(AllowedEmail.id == invite_uuid).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    db.delete(invite)
    db.commit()
    
    return {"message": "Invite removed successfully"}
