"""
Email Intake Schemas

Pydantic models for:
- Brevo webhook payload parsing (matches actual API docs)
- API responses for email logs

Reference: https://developers.brevo.com/docs/inbound-parse-webhooks
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Brevo Webhook Payload Schemas (matches actual API structure)
# -----------------------------------------------------------------------------

class BrevoMailbox(BaseModel):
    """Email address from Brevo webhook (Mailbox object)."""
    Address: str
    Name: Optional[str] = None


class BrevoAttachment(BaseModel):
    """Attachment metadata from Brevo webhook."""
    Name: str
    ContentType: str
    ContentLength: int
    ContentID: Optional[str] = None  # For inline images
    DownloadToken: str  # Token to fetch attachment via API


class BrevoEmailItem(BaseModel):
    """
    Single email item from Brevo inbound webhook.
    
    This is the structure inside the 'items' array.
    """
    # IDs
    Uuid: List[str] = Field(default_factory=list)  # List of recipient UUIDs
    MessageId: str
    InReplyTo: Optional[str] = None
    
    # Participants
    From: BrevoMailbox
    To: List[BrevoMailbox] = []
    Recipients: List[str] = []  # RCPT TO recipients
    Cc: List[BrevoMailbox] = []
    ReplyTo: Optional[BrevoMailbox] = None
    
    # Content
    Subject: Optional[str] = None
    RawHtmlBody: Optional[str] = None
    RawTextBody: Optional[str] = None
    ExtractedMarkdownMessage: Optional[str] = None
    ExtractedMarkdownSignature: Optional[str] = None
    
    # Metadata
    SentAtDate: Optional[str] = None  # RFC822 format
    SpamScore: Optional[float] = Field(None, alias="Spam.Score")
    
    # Attachments
    Attachments: List[BrevoAttachment] = []
    
    # Headers (can be string or list of strings)
    Headers: Dict[str, Any] = {}
    
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow"
    )
    
    @property
    def sender_email(self) -> str:
        """Get sender email address (lowercase)."""
        return self.From.Address.lower()
    
    @property
    def sender_name(self) -> Optional[str]:
        """Get sender name if available."""
        return self.From.Name
    
    @property
    def first_uuid(self) -> Optional[str]:
        """Get first UUID for idempotency."""
        return self.Uuid[0] if self.Uuid else None


class BrevoInboundWebhook(BaseModel):
    """
    Main Brevo inbound email webhook payload.
    
    The payload contains an 'items' array with email objects.
    Reference: https://developers.brevo.com/docs/inbound-parse-webhooks
    """
    items: List[BrevoEmailItem]
    
    model_config = ConfigDict(
        extra="allow"
    )
    
    @property
    def first_email(self) -> Optional[BrevoEmailItem]:
        """Get the first email item (most common case)."""
        return self.items[0] if self.items else None


# -----------------------------------------------------------------------------
# API Response Schemas
# -----------------------------------------------------------------------------

class EmailAttachmentResponse(BaseModel):
    """Attachment info for API responses."""
    id: UUID
    filename: str
    content_type: Optional[str]
    size_bytes: Optional[int]
    status: str
    document_id: Optional[UUID] = None
    
    model_config = ConfigDict(from_attributes=True)


class EmailLogResponse(BaseModel):
    """Email processing log for API responses."""
    id: UUID
    webhook_id: str
    sender_email: str
    sender_name: Optional[str]
    subject: Optional[str]
    status: str
    error_message: Optional[str] = None
    attachment_count: int
    documents_created: int
    received_at: datetime
    processed_at: Optional[datetime] = None
    
    # Related entities
    case_id: Optional[UUID] = None
    user_id: Optional[str] = None
    organization_id: Optional[UUID] = None
    
    # Nested attachments (optional, for detail view)
    attachments: List[EmailAttachmentResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class EmailStatsResponse(BaseModel):
    """Dashboard statistics for email intake."""
    total: int = 0
    authorized: int = 0
    unauthorized: int = 0
    processed: int = 0
    failed: int = 0


class WebhookAcceptedResponse(BaseModel):
    """Response returned immediately to Brevo."""
    status: str = "accepted"
    message_id: str
