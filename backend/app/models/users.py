import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Uuid, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.schemas.enums import UserRole

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="organization")
    cases = relationship("Case", back_populates="organization")
    clients = relationship("Client", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    id = Column(String(128), primary_key=True) # Firebase UID
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    
    organization = relationship("Organization", back_populates="users")

class AllowedEmail(Base):
    """Whitelist for Invite-Only Auth"""
    __tablename__ = "allowed_emails"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    role = Column(SAEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    organization = relationship("Organization")
