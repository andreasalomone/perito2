"""
Email Intake Service

Core business logic for processing inbound emails from Brevo webhook.
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Case, 
    Document, 
    User,
    EmailProcessingLog, 
    EmailAttachment, 
    BrevoWebhookLog,
)
from app.schemas.email_intake import BrevoInboundWebhook, BrevoEmailItem, BrevoAttachment
from app.schemas.enums import CaseStatus, ExtractionStatus
from app.services.gcs_service import get_storage_client
from app.services.case_service import trigger_extraction_task


logger = logging.getLogger(__name__)

# Brevo API base URL for fetching attachments
BREVO_INBOUND_API = "https://api.brevo.com/v3/inbound/events"


@dataclass
class UserLookupResult:
    """
    Simple result from user email lookup.
    Used because RLS bypass returns raw rows, not ORM objects.
    """
    id: str
    organization_id: UUID
    email: str


class EmailIntakeService:
    """
    Service for processing inbound emails from Brevo.
    
    Flow:
    1. Check idempotency (prevent duplicate processing)
    2. Look up sender in users table
    3. If authorized: create case, upload attachments, trigger AI
    4. If unauthorized: log and return
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def process_inbound_email(self, payload: BrevoInboundWebhook) -> Dict:
        """
        Main entry point for processing an inbound email.
        
        Brevo sends payload with 'items' array containing email objects.
        Returns dict with processing result.
        """
        # Get the first email from items array
        email_item = payload.first_email
        if not email_item:
            logger.warning("Received empty webhook payload")
            return {"status": "error", "reason": "empty payload"}
        
        # Use MessageId for idempotency (unique per email)
        message_id = email_item.MessageId
        sender_email = email_item.sender_email
        
        logger.info(f"Processing email message_id={message_id} from={sender_email}")
        
        try:
            # 1. Idempotency check
            if self._is_webhook_processed(message_id):
                logger.info(f"Message {message_id} already processed, skipping")
                return {"status": "skipped", "reason": "duplicate message"}
            
            # 2. Log webhook receipt (returns log for later update)
            webhook_log = self._log_webhook(message_id, payload)
            
            # 3. Look up user by sender email
            user = self._get_user_by_email(sender_email)
            
            if not user:
                # Unauthorized - log and return
                self._log_unauthorized_email(email_item)
                logger.warning(f"Unauthorized email from {sender_email}")
                return {"status": "unauthorized", "sender": sender_email}
            
            # 4. Set RLS context for this user's organization
            org_id = user.organization_id
            self.db.execute(text(f"SET LOCAL app.current_org_id = '{org_id}'"))
            
            # 5. Create email processing log entry
            email_log = self._create_email_log(email_item, user, status="authorized")
            
            # 6. Parse subject for case reference
            reference_code = self._parse_subject_line(email_item.Subject or "")
            
            # 7. Find or create case
            case = self._find_or_create_case(
                org_id=org_id,
                creator_id=user.id,
                reference_code=reference_code,
                subject=email_item.Subject
            )
            email_log.case_id = case.id
            
            # 8. Process attachments
            documents_created = 0
            for attachment in email_item.Attachments:
                try:
                    doc = self._process_attachment(
                        attachment=attachment,
                        email_log=email_log,
                        case=case,
                        org_id=org_id
                    )
                    if doc:
                        documents_created += 1
                        # 9. Trigger AI extraction for each document
                        trigger_extraction_task(doc.id, str(org_id))
                except Exception as e:
                    logger.error(f"Failed to process attachment {attachment.Name}: {e}")
                    # Continue with other attachments
            
            # 10. Update email log and webhook log
            email_log.status = "processed"
            email_log.documents_created = documents_created
            email_log.processed_at = datetime.now(timezone.utc)
            
            # Mark webhook as processed (idempotency)
            webhook_log.processed = True
            
            self.db.commit()
            
            logger.info(f"Email processed: message_id={message_id}, case={case.id}, docs={documents_created}")
            
            return {
                "status": "processed",
                "case_id": str(case.id),
                "documents_created": documents_created
            }
            
        except Exception as e:
            logger.error(f"Email processing failed: {e}", exc_info=True)
            self.db.rollback()
            
            # Try to update email log with error
            try:
                self._update_email_log_error(message_id, str(e))
            except Exception:
                pass  # Best effort
            
            raise
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _is_webhook_processed(self, message_id: str) -> bool:
        """Check if message was already processed (idempotency)."""
        result = self.db.execute(
            select(BrevoWebhookLog).where(BrevoWebhookLog.webhook_id == message_id)
        )
        return result.scalar_one_or_none() is not None
    
    def _log_webhook(self, message_id: str, payload: BrevoInboundWebhook) -> BrevoWebhookLog:
        """Log webhook receipt for idempotency tracking."""
        payload_hash = hashlib.sha256(
            payload.model_dump_json().encode()
        ).hexdigest()
        
        webhook_log = BrevoWebhookLog(
            webhook_id=message_id,
            event_type="inbound_email",
            payload_hash=payload_hash,
            processed=False
        )
        self.db.add(webhook_log)
        self.db.flush()
        return webhook_log
    
    def _get_user_by_email(self, email: str) -> Optional[UserLookupResult]:
        """
        Look up user by email address (case-insensitive).
        
        NOTE: This query bypasses RLS because no org context is set yet.
        Users table RLS uses user_self_access policy which would block this.
        We execute raw SQL to bypass RLS safely for this specific lookup.
        
        Returns UserLookupResult with id, organization_id, email.
        """
        result = self.db.execute(
            text("SELECT id, organization_id, email FROM users WHERE LOWER(email) = LOWER(:email)"),
            {"email": email}
        )
        row = result.fetchone()
        if row:
            return UserLookupResult(
                id=row.id,
                organization_id=row.organization_id,
                email=row.email
            )
        return None
    
    def _log_unauthorized_email(self, email_item: BrevoEmailItem):
        """Log an unauthorized email attempt."""
        email_log = self._create_email_log(email_item, user=None, status="unauthorized")
        self.db.commit()
    
    def _create_email_log(
        self, 
        email_item: BrevoEmailItem, 
        user: Optional[UserLookupResult],
        status: str
    ) -> EmailProcessingLog:
        """Create email processing log entry."""
        email_log = EmailProcessingLog(
            webhook_id=email_item.MessageId,
            sender_email=email_item.sender_email,
            sender_name=email_item.sender_name,
            subject=email_item.Subject,
            message_id=email_item.MessageId,
            status=status,
            attachment_count=len(email_item.Attachments),
            organization_id=user.organization_id if user else None,
            user_id=user.id if user else None,
        )
        self.db.add(email_log)
        self.db.flush()
        return email_log
    
    def _parse_subject_line(self, subject: str) -> Optional[str]:
        """
        Extract case reference code from email subject.
        
        Patterns supported:
        - "Sinistro ABC123"
        - "Pratica XYZ-001"
        - "Rif. ABC-123"
        - "Ns. Rif. 12345"
        """
        if not subject:
            return None
        
        # Clean up RE:/FWD: prefixes
        subject = re.sub(r'^(RE:|FWD:|R:|I:)\s*', '', subject, flags=re.IGNORECASE)
        
        # Pattern 1: Sinistro/Pratica followed by code
        match = re.search(
            r'(?:sinistro|pratica|rif\.?|ns\.?\s*rif\.?)\s*[:\s]*([A-Z0-9][-A-Z0-9/]*)',
            subject,
            re.IGNORECASE
        )
        if match:
            return match.group(1).upper().strip()
        
        # Pattern 2: Any alphanumeric code at start
        match = re.match(r'^([A-Z0-9][-A-Z0-9/]{2,})', subject, re.IGNORECASE)
        if match:
            return match.group(1).upper().strip()
        
        return None
    
    def _find_or_create_case(
        self,
        org_id: UUID,
        creator_id: str,
        reference_code: Optional[str],
        subject: Optional[str]
    ) -> Case:
        """Find existing case by reference code or create new one."""
        
        if reference_code:
            # Try to find existing case with this reference code
            result = self.db.execute(
                select(Case).where(
                    Case.organization_id == org_id,
                    Case.reference_code == reference_code,
                    Case.deleted_at.is_(None)
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.info(f"Found existing case {existing.id} for reference {reference_code}")
                return existing
        
        # Create new case
        case = Case(
            organization_id=org_id,
            creator_id=creator_id,
            reference_code=reference_code or self._generate_email_reference(),
            status=CaseStatus.OPEN,
        )
        self.db.add(case)
        self.db.flush()
        
        logger.info(f"Created new case {case.id} for email")
        return case
    
    def _generate_email_reference(self) -> str:
        """Generate a unique reference code for emails without one."""
        import uuid as uuid_module
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        short_uuid = str(uuid_module.uuid4())[:8].upper()
        return f"EMAIL-{timestamp}-{short_uuid}"
    
    def _process_attachment(
        self,
        attachment: BrevoAttachment,
        email_log: EmailProcessingLog,
        case: Case,
        org_id: UUID
    ) -> Optional[Document]:
        """
        Download attachment from Brevo using DownloadToken and upload to GCS.
        Returns Document if successful, None otherwise.
        """
        # Validate file type
        if attachment.ContentType and attachment.ContentType not in settings.ALLOWED_MIME_TYPES.values():
            logger.warning(f"Skipping unsupported file type: {attachment.ContentType} for {attachment.Name}")
            return None
        
        # Create email attachment record
        email_attach = EmailAttachment(
            email_log_id=email_log.id,
            organization_id=org_id,
            filename=attachment.Name,
            content_type=attachment.ContentType,
            size_bytes=attachment.ContentLength,
            brevo_download_url=f"token:{attachment.DownloadToken}",  # Store token reference
            status="pending"
        )
        self.db.add(email_attach)
        self.db.flush()
        
        try:
            # Download from Brevo using token
            file_content = self._download_attachment_with_token(attachment.DownloadToken)
            email_attach.status = "downloaded"
            
            # Upload to GCS
            gcs_path = self._upload_to_gcs(
                content=file_content,
                filename=attachment.Name,
                case_id=case.id,
                org_id=org_id
            )
            email_attach.gcs_path = gcs_path
            email_attach.status = "uploaded"
            
            # Create document record
            doc = self._create_document_record(
                case_id=case.id,
                org_id=org_id,
                filename=attachment.Name,
                gcs_path=gcs_path,
                mime_type=attachment.ContentType
            )
            
            # Link attachment to document
            email_attach.document_id = doc.id
            email_attach.status = "linked"
            
            return doc
            
        except Exception as e:
            email_attach.status = "failed"
            email_attach.download_error = str(e)
            logger.error(f"Attachment processing failed: {e}")
            return None
    
    def _download_attachment_with_token(self, download_token: str) -> bytes:
        """
        Download attachment content using Brevo's attachment API.
        
        Reference: https://developers.brevo.com/reference/get_inbound_attachments-by-download-token
        """
        if not download_token:
            raise ValueError("No download token provided")
        
        if not settings.BREVO_API_KEY:
            raise ValueError("BREVO_API_KEY not configured")
        
        url = f"https://api.brevo.com/v3/inbound/attachments/{download_token}"
        headers = {
            "api-key": settings.BREVO_API_KEY,
            "accept": "application/octet-stream"
        }
        
        with httpx.Client(timeout=120.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
    
    def _upload_to_gcs(
        self,
        content: bytes,
        filename: str,
        case_id: UUID,
        org_id: UUID
    ) -> str:
        """Upload file content to GCS and return gs:// path."""
        client = get_storage_client()
        bucket = client.bucket(settings.STORAGE_BUCKET_NAME)
        
        # Use same path format as existing documents
        blob_name = f"uploads/{org_id}/{case_id}/{filename}"
        blob = bucket.blob(blob_name)
        
        blob.upload_from_string(content)
        
        # Mark as finalized
        blob.metadata = {"status": "finalized", "source": "email"}
        blob.patch()
        
        return f"gs://{settings.STORAGE_BUCKET_NAME}/{blob_name}"
    
    def _create_document_record(
        self,
        case_id: UUID,
        org_id: UUID,
        filename: str,
        gcs_path: str,
        mime_type: Optional[str]
    ) -> Document:
        """Create document record in database."""
        doc = Document(
            case_id=case_id,
            organization_id=org_id,
            filename=filename,
            gcs_path=gcs_path,
            mime_type=mime_type,
            ai_status=ExtractionStatus.PENDING
        )
        self.db.add(doc)
        self.db.flush()
        return doc
    
    def _update_email_log_error(self, message_id: str, error_message: str):
        """Update email log with error status."""
        result = self.db.execute(
            select(EmailProcessingLog).where(
                EmailProcessingLog.webhook_id == message_id
            )
        )
        email_log = result.scalar_one_or_none()
        if email_log:
            email_log.status = "failed"
            email_log.error_message = error_message
            self.db.commit()
