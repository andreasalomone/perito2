import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.schemas.enums import ExtractionStatus

if TYPE_CHECKING:
    from app.models.cases import Case


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_case_status", "case_id", "ai_status"),
        Index("idx_documents_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    gcs_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # AI Data (The "Brain")
    ai_status: Mapped[ExtractionStatus] = mapped_column(
        default=ExtractionStatus.PENDING, nullable=False
    )
    ai_extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    case: Mapped["Case"] = relationship("Case", back_populates="documents")



class ReportVersion(Base):
    """Stores history: v1 (AI), v2 (Human Edit), v3 (Final)"""

    __tablename__ = "report_versions"
    __table_args__ = (Index("idx_report_versions_case", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    docx_storage_path: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)

    # Provenance
    ai_raw_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    case: Mapped["Case"] = relationship("Case", back_populates="report_versions")
