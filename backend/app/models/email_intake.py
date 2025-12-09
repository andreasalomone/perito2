"""
Email Intake Models

SQLAlchemy models for:
- EmailProcessingLog: tracks all inbound emails
- EmailAttachment: tracks attachments from emails
- BrevoWebhookLog: prevents duplicate webhook processing
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.cases import Case
    from app.models.documents import Document
    from app.models.users import Organization, User


class EmailProcessingLog(Base):
    """
    Tracks all inbound emails received via Brevo webhook.
    Each email is logged regardless of authorization status.
    """

    __tablename__ = "email_processing_log"
    __table_args__ = (
        Index("idx_email_log_org_received", "organization_id", "received_at"),
        Index("idx_email_log_status", "status"),
        Index("idx_email_log_sender", "sender_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Tenant context (nullable for unauthorized emails)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )

    # User who sent the email (nullable for unauthorized)
    # Note: users.id is VARCHAR(128), not UUID
    user_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Case created/updated by this email
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )

    # Brevo webhook unique identifier (for idempotency)
    webhook_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Email metadata
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Processing status: 'received', 'authorized', 'unauthorized', 'processed', 'failed'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="received")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Counts
    attachment_count: Mapped[int] = mapped_column(Integer, default=0)
    documents_created: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    user: Mapped[Optional["User"]] = relationship(back_populates="email_logs")
    case: Mapped[Optional["Case"]] = relationship(back_populates="email_logs")
    attachments: Mapped[List["EmailAttachment"]] = relationship(
        back_populates="email_log", cascade="all, delete-orphan"
    )


class EmailAttachment(Base):
    """
    Tracks attachments downloaded from inbound emails.
    Links to documents table after document creation.
    """

    __tablename__ = "email_attachments"
    __table_args__ = (
        Index("idx_email_attach_log", "email_log_id"),
        Index("idx_email_attach_doc", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Parent email log
    email_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_processing_log.id", ondelete="CASCADE"), nullable=False
    )

    # Tenant context
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )

    # Link to created document (set after document creation)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    # Attachment metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Storage - matches documents.gcs_path format
    gcs_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    brevo_download_url: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True
    )

    # Processing status: 'pending', 'downloaded', 'uploaded', 'linked', 'failed'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    download_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    email_log: Mapped["EmailProcessingLog"] = relationship(back_populates="attachments")
    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    document: Mapped[Optional["Document"]] = relationship("Document")


class BrevoWebhookLog(Base):
    """
    Idempotency log for Brevo webhooks.
    Prevents duplicate processing when Brevo retries.
    Does NOT have RLS - global deduplication table.
    """

    __tablename__ = "brevo_webhook_log"
    __table_args__ = (Index("idx_brevo_webhook_id", "webhook_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Brevo's unique webhook identifier
    webhook_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Event metadata
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Processing flag
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
