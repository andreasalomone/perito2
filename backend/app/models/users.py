import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Uuid,
    func,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.schemas.enums import UserRole

# Prevent circular imports for type checking
if TYPE_CHECKING:
    from app.models.cases import Case
    from app.models.client import Client
    from app.models.email_intake import EmailProcessingLog

class Organization(Base):
    """
    The Tenant Root.
    """
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    
    # Relationships
    # Explicit 'List[Type]' typing enables IDE navigation
    users: Mapped[List["User"]] = relationship(
        back_populates="organization", 
        cascade="all, delete-orphan"
    )
    cases: Mapped[List["Case"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    clients: Mapped[List["Client"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    # Added missing relationship to support 'GET /admin/organizations/{id}/invites'
    invites: Mapped[List["AllowedEmail"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan"
    )


class User(Base):
    """
    Authenticated User (synced from Firebase).
    Enforces strict 1-User-1-Org membership.
    """
    __tablename__ = "users"

    # Firebase UID is the Primary Key
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    
    # Index added for fast lookup during Auth Sync
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    
    role: Mapped[UserRole] = mapped_column(
        default=UserRole.MEMBER, nullable=False
    )
    
    # Profile fields for onboarding
    first_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    last_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    
    # Audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    organization: Mapped["Organization"] = relationship(back_populates="users")
    cases: Mapped[List["Case"]] = relationship(back_populates="creator")
    email_logs: Mapped[List["EmailProcessingLog"]] = relationship(back_populates="user")
    
    @property
    def is_profile_complete(self) -> bool:
        """Returns True if both first_name and last_name are set."""
        return bool(self.first_name and self.last_name)
    



class AllowedEmail(Base):
    """
    Whitelist / Invitation System.
    """
    __tablename__ = "allowed_emails"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    
    # Global uniqueness enforces that an email can only be invited 
    # to one organization at a time (Strict Tenancy).
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    
    role: Mapped[UserRole] = mapped_column(
        default=UserRole.MEMBER, nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    
    organization: Mapped["Organization"] = relationship(back_populates="invites")
