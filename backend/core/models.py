import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

# Import Base from your new database configuration
# Note: We use absolute import assuming running from 'backend/' root
from database import Base

class UserRole(enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"

class ReportStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    PROCESSING = "processing"

class ExtractionStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
    PROCESSING = "processing"

class Organization(Base):
    __tablename__ = "organization"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="organization")
    reports = relationship("ReportLog", back_populates="organization")

    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"

class User(Base):
    __tablename__ = "user"

    id = Column(String(128), primary_key=True) # Firebase UID
    email = Column(String(255), nullable=False, unique=True)
    organization_id = Column(String(36), ForeignKey("organization.id"), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.ADMIN)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', org={self.organization_id})>"

class ReportLog(Base):
    __tablename__ = "report_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # --- NEW: Multi-tenancy Field ---
    # Stores the Firebase UID (User ID) to secure data access
    user_id = Column(String(128), nullable=False, index=True) 
    organization_id = Column(String(36), ForeignKey("organization.id"), nullable=True) # Made nullable for migration, but should be populated
    
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(ReportStatus), nullable=False, default=ReportStatus.PROCESSING)
    
    generation_time_seconds = Column(Float, nullable=True)
    api_cost_usd = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    # Real-time progress tracking
    # Changed db.JSON to standard sqlalchemy JSON
    progress_logs = Column(JSON, default=list) 
    current_step = Column(String(50), default="queued")

    # Token usage details
    prompt_token_count = Column(Integer, nullable=True)
    candidates_token_count = Column(Integer, nullable=True)
    total_token_count = Column(Integer, nullable=True)
    cached_content_token_count = Column(Integer, nullable=True)

    # Content
    llm_raw_response = Column(Text, nullable=True)
    final_report_text = Column(Text, nullable=True)
    
    # Link to the final DOCX in Cloud Storage (Optional, good for history)
    final_docx_path = Column(String(1024), nullable=True)

    # Relationships
    documents = relationship("DocumentLog", back_populates="report", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="reports")

    def __repr__(self):
        return f"<ReportLog(id={self.id}, user={self.user_id}, status='{self.status}')>"

class DocumentLog(Base):
    __tablename__ = "document_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey("report_log.id"), nullable=False)

    original_filename = Column(String(255), nullable=False)
    
    # This will now store the 'gs://' path or the blob name
    stored_filepath = Column(String(1024), nullable=False) 
    
    file_size_bytes = Column(Integer, nullable=False)

    # Tracking
    extraction_status = Column(Enum(ExtractionStatus), default=ExtractionStatus.PROCESSING)
    extracted_content_length = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    file_type = Column(String(50), nullable=True)
    extraction_method = Column(String(50), nullable=True)

    # Relationships
    report = relationship("ReportLog", back_populates="documents")

    def __repr__(self):
        return f"<DocumentLog(id={self.id}, filename='{self.original_filename}')>"

class PricingConfig(Base):
    __tablename__ = "pricing_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Integer, default=1) # 1 = active, 0 = inactive
    
    # Input Prices (per 1M tokens)
    price_input_tier_1 = Column(Float, default=1.25) # <= 128k
    price_input_tier_2 = Column(Float, default=2.50) # > 128k
    
    # Output Prices (per 1M tokens)
    price_output_tier_1 = Column(Float, default=3.75) # <= 128k
    price_output_tier_2 = Column(Float, default=7.50) # > 128k
    
    # Cache Prices (per 1M tokens)
    price_cache_tier_1 = Column(Float, default=0.30)
    price_cache_tier_2 = Column(Float, default=0.60)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PricingConfig(id={self.id}, active={self.active})>"