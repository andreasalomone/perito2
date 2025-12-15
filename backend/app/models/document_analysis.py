"""
Document Analysis Model
=======================
Stores AI-generated document analysis results with staleness tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.cases import Case


class DocumentAnalysis(Base):
    """
    Stores document analysis results for the "Early Analysis" feature.

    Each case can have multiple analyses (history), but typically only the
    latest is displayed. The `document_hash` enables staleness detection:
    if documents are added/removed, the hash changes and analysis becomes stale.
    """

    __tablename__ = "document_analyses"
    __table_args__ = (
        Index("idx_document_analyses_case", "case_id"),
        Index("idx_document_analyses_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False
    )

    # Analysis Content
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    received_docs: Mapped[List] = mapped_column(JSONB, nullable=False, default=list)
    missing_docs: Mapped[List] = mapped_column(JSONB, nullable=False, default=list)

    # Staleness Detection
    # SHA-256 hash of sorted document IDs at time of analysis
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="document_analyses")
