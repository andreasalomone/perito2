import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid, JSON
from sqlalchemy.orm import Mapped, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AuditLog(Base):
    """Tracks critical user actions and system events for compliance and debugging."""
    __tablename__ = "audit_logs"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True) # Nullable for system actions
    
    action = Column(String(50), nullable=False) # e.g. "LOGIN", "CREATE_CASE", "GENERATE_REPORT"
    resource_type = Column(String(50)) # e.g. "CASE", "DOCUMENT"
    resource_id = Column(Uuid) # ID of the affected resource
    
    details = Column(JSON) # Flexible storage for metadata (e.g. tokens, cost, diffs)
    ip_address = Column(String(45))
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped[Optional["User"]] = relationship("User")
