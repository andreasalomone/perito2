import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Uuid, Enum as SAEnum, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.schemas.enums import CaseStatus

class Client(Base):
    """CRM: The Insurance Companies"""
    __tablename__ = "clients"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False) # e.g. "Generali"
    vat_number = Column(String(50))
    
    __table_args__ = (UniqueConstraint('organization_id', 'name', name='uq_clients_org_name'),)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    organization = relationship("Organization", back_populates="clients")
    cases = relationship("Case", back_populates="client")

class Case(Base):
    """The Container for a Claim (Sinistro)"""
    __tablename__ = "cases"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    client_id = Column(Uuid, ForeignKey("clients.id"), nullable=True)
    creator_id = Column(String(128), ForeignKey("users.id"), nullable=True)
    
    reference_code = Column(String(100)) # e.g. "Sinistro 2024/005"
    status = Column(SAEnum(CaseStatus), default=CaseStatus.OPEN, nullable=False) # Checked by DB constraint
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_cases_dashboard', 'organization_id', text('created_at DESC')),
        Index('idx_cases_reference', 'organization_id', 'reference_code'),
        Index('idx_cases_client', 'organization_id', 'client_id'),
        Index('idx_cases_creator', 'organization_id', 'creator_id'),
    )

    # Relationships
    organization = relationship("Organization", back_populates="cases")
    client = relationship("Client", back_populates="cases")
    creator = relationship("User", backref="cases") # Backref for easy access
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    report_versions = relationship("ReportVersion", back_populates="case", cascade="all, delete-orphan")
