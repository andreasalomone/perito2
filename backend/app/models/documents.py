import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.schemas.enums import ExtractionStatus


class Document(Base):
    __tablename__ = "documents"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id = Column(Uuid, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)

    filename = Column(String(255), nullable=False)
    gcs_path = Column(String(1024), nullable=False)
    mime_type = Column(String(100))

    # AI Data (The "Brain")
    ai_status = Column(
        SAEnum(ExtractionStatus), default=ExtractionStatus.PENDING, nullable=False
    )
    ai_extracted_data = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_documents_case_status", "case_id", "ai_status"),
        Index("idx_documents_org", "organization_id"),
    )

    case = relationship("Case", back_populates="documents")


class ReportVersion(Base):
    """Stores history: v1 (AI), v2 (Human Edit), v3 (Final)"""

    __tablename__ = "report_versions"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id = Column(Uuid, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)

    version_number = Column(Integer, nullable=False)
    docx_storage_path = Column(String(1024))
    is_final = Column(Boolean, default=False)

    # Provenance
    ai_raw_output = Column(Text, nullable=True)  # If this was v1

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("idx_report_versions_case", "case_id"),)

    case = relationship("Case", back_populates="report_versions")
