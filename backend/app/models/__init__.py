import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, String, Boolean, ForeignKey, Integer, Text, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base

# --- TENANCY & CRM ---

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="organization")
    cases = relationship("Case", back_populates="organization")
    clients = relationship("Client", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    id = Column(String(128), primary_key=True) # Firebase UID
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    
    organization = relationship("Organization", back_populates="users")

class Client(Base):
    """CRM: The Insurance Companies"""
    __tablename__ = "clients"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False) # e.g. "Generali"
    vat_number = Column(String(50))
    
    __table_args__ = (UniqueConstraint('organization_id', 'name', name='uq_clients_org_name'),)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    organization = relationship("Organization", back_populates="clients")
    cases = relationship("Case", back_populates="client")

# --- WORKFLOW ENTITIES ---

class Case(Base):
    """The Container for a Claim (Sinistro)"""
    __tablename__ = "cases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    
    reference_code = Column(String(100)) # e.g. "Sinistro 2024/005"
    status = Column(String(50), default="open") # open, closed, archived
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="cases")
    client = relationship("Client", back_populates="cases")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    report_versions = relationship("ReportVersion", back_populates="case", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    filename = Column(String(255), nullable=False)
    gcs_path = Column(String(1024), nullable=False)
    mime_type = Column(String(100))
    
    # AI Data (The "Brain")
    ai_status = Column(String(50), default="pending")
    ai_extracted_data = Column(JSONB, nullable=True) 
    
    created_at = Column(DateTime, default=datetime.utcnow)
    case = relationship("Case", back_populates="documents")

class ReportVersion(Base):
    """Stores history: v1 (AI), v2 (Human Edit), v3 (Final)"""
    __tablename__ = "report_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    version_number = Column(Integer, nullable=False)
    docx_storage_path = Column(String(1024))
    is_final = Column(Boolean, default=False)
    
    # Provenance
    ai_raw_output = Column(Text, nullable=True) # If this was v1
    
    created_at = Column(DateTime, default=datetime.utcnow)
    case = relationship("Case", back_populates="report_versions")

class MLTrainingPair(Base):
    """The Gold Mine: Maps Inputs -> AI Draft -> Human Final"""
    __tablename__ = "ml_training_pairs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"))
    
    ai_version_id = Column(UUID(as_uuid=True), ForeignKey("report_versions.id"))
    final_version_id = Column(UUID(as_uuid=True), ForeignKey("report_versions.id"))
    
    quality_score = Column(Float) # Optional rating
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    """Tracks critical user actions and system events for compliance and debugging."""
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(128), ForeignKey("users.id"), nullable=True) # Nullable for system actions
    
    action = Column(String(50), nullable=False) # e.g. "LOGIN", "CREATE_CASE", "GENERATE_REPORT"
    resource_type = Column(String(50)) # e.g. "CASE", "DOCUMENT"
    resource_id = Column(UUID(as_uuid=True)) # ID of the affected resource
    
    details = Column(JSONB) # Flexible storage for metadata (e.g. tokens, cost, diffs)
    ip_address = Column(String(45))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User")