import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        Index(
            "idx_outbox_pending_fifo",
            "created_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index(
            "idx_outbox_org_pending",
            "organization_id",
            "created_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("idx_outbox_retry_count", "retry_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "generate_report"
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )  # The data needed for the task
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False
    )  # PENDING, PROCESSED, FAILED
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, nullable=True
    )  # For tenant isolation
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
