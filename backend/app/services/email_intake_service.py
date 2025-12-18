"""
Email Intake Service

Core business logic for processing inbound emails from Brevo webhook.
"""

import contextlib
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TypeVar
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    BrevoWebhookLog,
    Case,
    Client,
    Document,
    EmailAttachment,
    EmailProcessingLog,
)
from app.schemas.email_intake import (
    BrevoAttachment,
    BrevoEmailItem,
    BrevoInboundWebhook,
)
from app.schemas.enums import CaseStatus, ExtractionStatus
from app.services.case_service import trigger_extraction_task
from app.services.client_matcher import find_or_create_client
from app.services.email_ai_extractor import CaseExtractionResult, extract_case_data
from app.services.gcs_service import get_storage_client

# Client is already imported above from app.models


T = TypeVar("T")

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
        email_item = payload.first_email
        if not email_item:
            logger.warning("Received empty webhook payload")
            return {"status": "error", "reason": "empty payload"}

        message_id = email_item.MessageId
        sender_email = email_item.sender_email
        logger.info(f"Processing email message_id={message_id} from={sender_email}")

        try:
            return self._process_email_item(email_item, message_id, sender_email)
        except Exception as e:
            logger.error(f"Email processing failed: {e}", exc_info=True)
            self.db.rollback()
            self._safe_update_email_log_error(message_id, str(e))
            raise

    def _process_email_item(
        self, email_item: BrevoEmailItem, message_id: str, sender_email: str
    ) -> Dict:
        """Process a validated email item through the intake pipeline."""
        # 1. Idempotency check
        if self._is_webhook_processed(message_id):
            logger.info(f"Message {message_id} already processed, skipping")
            return {"status": "skipped", "reason": "duplicate message"}

        # 2. Log webhook receipt (hash based on email_item for idempotency)
        webhook_log = self._log_webhook(message_id, email_item)

        # 3. Authorize sender
        user = self._get_user_by_email(sender_email)
        if not user:
            self._log_unauthorized_email(email_item)
            logger.warning(f"Unauthorized email from {sender_email}")
            return {"status": "unauthorized", "sender": sender_email}

        # 4. Set RLS context
        org_id = user.organization_id
        self.db.execute(text(f"SET LOCAL app.current_org_id = '{org_id}'"))

        # 5. Create email log
        email_log = self._create_email_log(email_item, user, status="authorized")

        # 6. Process email content and attachments
        result = self._process_authorized_email(
            email_item=email_item,
            email_log=email_log,
            user=user,
            org_id=org_id,
        )

        # 7. Finalize logs
        email_log.status = "processed"
        email_log.documents_created = result["documents_created"]
        email_log.processed_at = datetime.now(timezone.utc)
        webhook_log.processed = True
        self.db.commit()

        logger.info(
            f"Email processed: message_id={message_id}, case={result['case'].id}, docs={result['documents_created']}"
        )

        return {
            "status": "processed",
            "case_id": str(result["case"].id),
            "documents_created": result["documents_created"],
        }

    def _process_authorized_email(
        self,
        email_item: BrevoEmailItem,
        email_log: EmailProcessingLog,
        user: UserLookupResult,
        org_id: UUID,
    ) -> Dict:
        """Process an authorized email: download attachments, extract data, create case."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            # Download and pre-process attachments
            attachments = email_item.Attachments or []
            downloaded_files_map, processed_attachments = (
                self._download_and_preprocess_attachments(
                    attachments=attachments,
                    temp_dir=temp_dir,
                )
            )

            # AI extraction
            extracted = self._run_ai_extraction(
                email_item=email_item,
                sender_email=email_item.sender_email,
                attachments=processed_attachments,
            )

            # Create or find case
            case = self._prepare_case(
                email_item=email_item,
                extracted=extracted,
                org_id=org_id,
                user=user,
            )
            email_log.case_id = case.id

            # Persist attachments to GCS
            documents_created = self._persist_attachments_to_gcs(
                attachments=attachments,
                downloaded_files_map=downloaded_files_map,
                email_log=email_log,
                case=case,
                org_id=org_id,
            )

        return {"case": case, "documents_created": documents_created}

    def _download_and_preprocess_attachments(
        self,
        attachments: list,
        temp_dir: str,
    ) -> tuple[Dict[str, str], list]:
        """Download attachments and process them for LLM context."""

        from app.services import document_processor

        downloaded_files_map: Dict[str, str] = {}
        processed_for_llm: list = []

        if not attachments:
            return downloaded_files_map, processed_for_llm

        logger.info(f"Pre-processing {len(attachments)} attachments for AI context...")

        for attachment in attachments:
            result = self._download_single_attachment(attachment, temp_dir)
            if result is None:
                continue

            local_path = result
            downloaded_files_map[attachment.Name] = local_path

            # Process for LLM (safe mode)
            try:
                if processed_data := document_processor.process_uploaded_file(
                    local_path, temp_dir
                ):
                    processed_for_llm.extend(processed_data)
            except Exception as proc_error:
                logger.warning(
                    f"Failed to process attachment {attachment.Name} for LLM context: {proc_error}"
                )

        return downloaded_files_map, processed_for_llm

    def _download_single_attachment(
        self, attachment: BrevoAttachment, temp_dir: str
    ) -> Optional[str]:
        """Download a single attachment to temp directory. Returns local path or None."""
        import os

        from app.services import document_processor

        # Filter unsupported types early
        if (
            attachment.ContentType
            and attachment.ContentType not in settings.ALLOWED_MIME_TYPES.values()
        ):
            logger.debug(
                f"Skipping unsupported type {attachment.ContentType} for {attachment.Name}"
            )
            return None

        try:
            safe_name = document_processor.sanitize_filename(attachment.Name)
            local_path = os.path.join(temp_dir, safe_name)

            # Streaming download directly to disk
            self._download_attachment_to_file(attachment.DownloadToken, local_path)

            return local_path
        except Exception as e:
            logger.warning(
                f"Failed to download/save attachment {attachment.Name} for pre-processing: {e}"
            )
            return None

    def _run_ai_extraction(
        self,
        email_item: BrevoEmailItem,
        sender_email: str,
        attachments: list,
    ) -> CaseExtractionResult:
        """Run AI extraction on email content and attachments."""
        markdown_body = (
            email_item.ExtractedMarkdownMessage or email_item.RawTextBody or ""
        )
        subject_line = email_item.Subject

        try:
            extracted = extract_case_data(
                email_body=markdown_body,
                subject=subject_line,
                sender_email=sender_email,
                attachments=attachments,
            )
        except Exception as e:
            logger.error(f"AI Extraction failed: {e}")
            extracted = None

        self._log_extraction_result(extracted)
        return extracted or CaseExtractionResult(extraction_success=False)

    def _log_extraction_result(self, extracted: Optional[CaseExtractionResult]) -> None:
        """Log the result of AI extraction."""
        if extracted and extracted.extraction_success:
            logger.info(
                f"AI extracted: ref={extracted.reference_code}, cliente={extracted.cliente}"
            )
        elif extracted:
            logger.warning(f"AI extraction failed: {extracted.error_message}")
        else:
            logger.warning("AI extraction could not be performed due to an error.")

    def _prepare_case(
        self,
        email_item: BrevoEmailItem,
        extracted: CaseExtractionResult,
        org_id: UUID,
        user: UserLookupResult,
    ) -> Case:
        """Find or create a case with extracted data."""
        # Fuzzy match or create client
        client = None
        if extracted.cliente:
            client = find_or_create_client(self.db, org_id, extracted.cliente)

        # Get reference code
        ref_from_subject = self._parse_subject_line(email_item.Subject or "")
        reference_code = extracted.reference_code or ref_from_subject

        return self._find_or_create_case_with_data(
            org_id=org_id,
            creator_id=user.id,
            reference_code=reference_code,
            extracted=extracted,
            client=client,
        )

    def _persist_attachments_to_gcs(
        self,
        attachments: list,
        downloaded_files_map: Dict[str, str],
        email_log: EmailProcessingLog,
        case: Case,
        org_id: UUID,
    ) -> int:
        """Persist downloaded attachments to GCS and create document records."""
        documents_created = 0

        for attachment in attachments:
            try:
                local_file_path = downloaded_files_map.get(attachment.Name)
                if doc := self._process_attachment(
                    attachment=attachment,
                    email_log=email_log,
                    case=case,
                    org_id=org_id,
                    pre_downloaded_path=local_file_path,
                ):
                    documents_created += 1
                    trigger_extraction_task(doc.id, str(org_id))
            except Exception as e:
                logger.error(
                    f"Failed to finalize processing attachment {attachment.Name}: {e}"
                )

        return documents_created

    def _safe_update_email_log_error(self, message_id: str, error_message: str) -> None:
        """Safely update email log with error (best effort)."""
        with contextlib.suppress(Exception):
            self._update_email_log_error(message_id, error_message)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _is_webhook_processed(self, message_id: str) -> bool:
        """Check if message was already processed (idempotency)."""
        result = self.db.execute(
            select(BrevoWebhookLog).where(BrevoWebhookLog.webhook_id == message_id)
        )
        return result.scalar_one_or_none() is not None

    def _log_webhook(
        self, message_id: str, email_item: BrevoEmailItem
    ) -> BrevoWebhookLog:
        """Log webhook receipt for idempotency tracking."""
        # Use email_item for hashing since we don't have the full payload here
        payload_hash = hashlib.sha256(email_item.model_dump_json().encode()).hexdigest()

        webhook_log = BrevoWebhookLog(
            webhook_id=message_id,
            event_type="inbound_email",
            payload_hash=payload_hash,
            processed=False,
        )
        return self._add_and_flush(webhook_log)

    def _get_user_by_email(self, email: str) -> Optional[UserLookupResult]:
        """
        Look up user by email address (case-insensitive).

        NOTE: This query bypasses RLS because no org context is set yet.
        Users table RLS uses user_self_access policy which would block this.
        We execute raw SQL to bypass RLS safely for this specific lookup.

        Returns UserLookupResult with id, organization_id, email.
        """
        result = self.db.execute(
            text(
                "SELECT id, organization_id, email FROM users WHERE LOWER(email) = LOWER(:email)"
            ),
            {"email": email},
        )
        row = result.fetchone()
        if row:
            return UserLookupResult(
                id=row.id, organization_id=row.organization_id, email=row.email
            )
        return None

    def _log_unauthorized_email(self, email_item: BrevoEmailItem):
        """Log an unauthorized email attempt."""
        self._create_email_log(email_item, user=None, status="unauthorized")
        self.db.commit()

    def _create_email_log(
        self, email_item: BrevoEmailItem, user: Optional[UserLookupResult], status: str
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
        return self._add_and_flush(email_log)

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
        subject = re.sub(r"^(RE:|FWD:|R:|I:)\s*", "", subject, flags=re.IGNORECASE)

        # Pattern 1: Sinistro/Pratica followed by code
        match = re.search(
            r"(?:sinistro|pratica|rif\.?|ns\.?\s*rif\.?)\s*[:\s]*([A-Z0-9][-A-Z0-9/]*)",
            subject,
            re.IGNORECASE,
        )
        if match:
            return match[1].upper().strip()

        # Pattern 2: Any alphanumeric code at start
        match = re.match(r"^([A-Z0-9][-A-Z0-9/]{2,})", subject, re.IGNORECASE)
        return match[1].upper().strip() if match else None

    def _find_or_create_case_with_data(
        self,
        org_id: UUID,
        creator_id: str,
        reference_code: Optional[str],
        extracted: CaseExtractionResult,
        client: Optional["Client"],
    ) -> Case:
        """
        Find existing case by reference code or create new one with AI-extracted fields.

        Applies all 25 business fields from AI extraction.
        """

        if reference_code:
            # Try to find existing case with this reference code
            result = self.db.execute(
                select(Case).where(
                    Case.organization_id == org_id,
                    Case.reference_code == reference_code,
                    Case.deleted_at.is_(None),
                )
            )
            if existing := result.scalar_one_or_none():
                # Update existing case with AI-extracted fields (if not already set)
                self._apply_extracted_fields(existing, extracted, client)
                logger.info(
                    f"Updated existing case {existing.id} with AI-extracted data"
                )
                return existing

        # Create new case with all AI-extracted fields
        case = Case(
            organization_id=org_id,
            creator_id=creator_id,
            reference_code=reference_code or self._generate_email_reference(),
            status=CaseStatus.OPEN,
            # Client link
            client_id=client.id if client else None,
            # All 25 business fields from AI extraction
            ns_rif=extracted.ns_rif,
            polizza=extracted.polizza,
            tipo_perizia=extracted.tipo_perizia,
            merce=extracted.merce,
            descrizione_merce=extracted.descrizione_merce,
            riserva=extracted.riserva,
            importo_liquidato=extracted.importo_liquidato,
            perito=extracted.perito,
            cliente=extracted.cliente,
            rif_cliente=extracted.rif_cliente,
            gestore=extracted.gestore,
            assicurato=extracted.assicurato,
            riferimento_assicurato=extracted.riferimento_assicurato,
            mittenti=extracted.mittenti,
            broker=extracted.broker,
            riferimento_broker=extracted.riferimento_broker,
            destinatari=extracted.destinatari,
            mezzo_di_trasporto=extracted.mezzo_di_trasporto,
            descrizione_mezzo_di_trasporto=extracted.descrizione_mezzo_di_trasporto,
            luogo_intervento=extracted.luogo_intervento,
            genere_lavorazione=extracted.genere_lavorazione,
            data_sinistro=extracted.data_sinistro,
            data_incarico=extracted.data_incarico,
            note=extracted.note,
        )
        self.db.add(case)
        self.db.flush()

        logger.info(f"Created new case {case.id} with AI-extracted data")
        return case

    def _apply_extracted_fields(
        self, case: Case, extracted: CaseExtractionResult, client: Optional["Client"]
    ):
        """Apply AI-extracted fields to existing case (only if field is empty)."""
        # Only update fields that are currently empty
        field_updates = [
            ("client_id", client.id if client else None),
            ("ns_rif", extracted.ns_rif),
            ("polizza", extracted.polizza),
            ("tipo_perizia", extracted.tipo_perizia),
            ("merce", extracted.merce),
            ("descrizione_merce", extracted.descrizione_merce),
            ("riserva", extracted.riserva),
            ("importo_liquidato", extracted.importo_liquidato),
            ("perito", extracted.perito),
            ("cliente", extracted.cliente),
            ("rif_cliente", extracted.rif_cliente),
            ("gestore", extracted.gestore),
            ("assicurato", extracted.assicurato),
            ("riferimento_assicurato", extracted.riferimento_assicurato),
            ("mittenti", extracted.mittenti),
            ("broker", extracted.broker),
            ("riferimento_broker", extracted.riferimento_broker),
            ("destinatari", extracted.destinatari),
            ("mezzo_di_trasporto", extracted.mezzo_di_trasporto),
            (
                "descrizione_mezzo_di_trasporto",
                extracted.descrizione_mezzo_di_trasporto,
            ),
            ("luogo_intervento", extracted.luogo_intervento),
            ("genere_lavorazione", extracted.genere_lavorazione),
            ("data_sinistro", extracted.data_sinistro),
            ("data_incarico", extracted.data_incarico),
            ("note", extracted.note),
        ]

        for field_name, new_value in field_updates:
            if new_value is not None and getattr(case, field_name, None) is None:
                setattr(case, field_name, new_value)

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
        org_id: UUID,
        pre_downloaded_path: Optional[str] = None,
    ) -> Optional[Document]:
        """
        Download attachment from Brevo using DownloadToken and upload to GCS.
        Returns Document if successful, None otherwise.
        """
        # Validate file type
        if (
            attachment.ContentType
            and attachment.ContentType not in settings.ALLOWED_MIME_TYPES.values()
        ):
            logger.warning(
                f"Skipping unsupported file type: {attachment.ContentType} for {attachment.Name}"
            )
            return None

        # Create email attachment record
        email_attach = EmailAttachment(
            email_log_id=email_log.id,
            organization_id=org_id,
            filename=attachment.Name,
            content_type=attachment.ContentType,
            size_bytes=attachment.ContentLength,
            brevo_download_url=f"token:{attachment.DownloadToken}",  # Store token reference
            status="pending",
        )
        self.db.add(email_attach)
        self.db.flush()

        try:
            # Download from Brevo (or use pre-downloaded)
            # If not pre-downloaded, we download to a temp file first to avoid RAM pressure
            if not (pre_downloaded_path and os.path.exists(pre_downloaded_path)):
                import tempfile

                # We use a temporary file to store the content during migration to GCS
                with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
                    pre_downloaded_path = tmp_f.name
                    self._download_attachment_to_file(
                        attachment.DownloadToken, pre_downloaded_path
                    )

            email_attach.status = "downloaded"

            # Upload to GCS using stream (from file)
            with open(pre_downloaded_path, "rb") as f:
                gcs_path = self._upload_stream_to_gcs(
                    file_obj=f,
                    filename=attachment.Name,
                    case_id=case.id,
                    org_id=org_id,
                )

            email_attach.gcs_path = gcs_path
            email_attach.status = "uploaded"

            # Create document record
            doc = self._create_document_record(
                case_id=case.id,
                org_id=org_id,
                filename=attachment.Name,
                gcs_path=gcs_path,
                mime_type=attachment.ContentType,
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

    def _download_attachment_to_file(
        self, download_token: str, target_path: str
    ) -> None:
        """
        Download attachment content using Brevo's attachment API in chunks.
        """
        if not download_token:
            raise ValueError("No download token provided")

        if not settings.BREVO_API_KEY:
            raise ValueError("BREVO_API_KEY not configured")

        url = f"https://api.brevo.com/v3/inbound/attachments/{download_token}"
        headers = {
            "api-key": settings.BREVO_API_KEY,
            "accept": "application/octet-stream",
        }

        # Use streaming to avoid loading large attachments into RAM
        with httpx.Client(timeout=120.0) as client:
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                with open(target_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

    def _upload_stream_to_gcs(
        self, file_obj: Any, filename: str, case_id: UUID, org_id: UUID
    ) -> str:
        """Upload file content to GCS from a file-like object and return gs:// path."""
        client = get_storage_client()
        bucket = client.bucket(settings.STORAGE_BUCKET_NAME)

        # Use same path format as existing documents
        blob_name = f"uploads/{org_id}/{case_id}/{filename}"
        blob = bucket.blob(blob_name)

        # upload_from_file uses a stream
        blob.upload_from_file(file_obj)

        # Mark as finalized
        blob.metadata = {"status": "finalized", "source": "email"}
        blob.patch()

        return f"gs://{settings.STORAGE_BUCKET_NAME}/{blob_name}"

    def _download_attachment_with_token(self, download_token: str) -> bytes:
        """
        DEPRECATED: Use _download_attachment_to_file for memory safety.
        Keep as fallback or for small metadata if needed.
        """
        import tempfile

        with tempfile.NamedTemporaryFile() as tmp:
            self._download_attachment_to_file(download_token, tmp.name)
            with open(tmp.name, "rb") as f:
                return f.read()

    def _upload_to_gcs(
        self, content: bytes, filename: str, case_id: UUID, org_id: UUID
    ) -> str:
        """
        DEPRECATED: Use _upload_stream_to_gcs for memory safety.
        """
        import io

        return self._upload_stream_to_gcs(
            io.BytesIO(content), filename, case_id, org_id
        )

    def _create_document_record(
        self,
        case_id: UUID,
        org_id: UUID,
        filename: str,
        gcs_path: str,
        mime_type: Optional[str],
    ) -> Document:
        """Create document record in database."""
        doc = Document(
            case_id=case_id,
            organization_id=org_id,
            filename=filename,
            gcs_path=gcs_path,
            mime_type=mime_type,
            ai_status=ExtractionStatus.PENDING,
        )
        return self._add_and_flush(doc)

    def _add_and_flush(self, entity: T) -> T:
        """Add an entity to the database session and flush to get its ID."""
        self.db.add(entity)
        self.db.flush()
        return entity

    def _update_email_log_error(self, message_id: str, error_message: str):
        """Update email log with error status."""
        result = self.db.execute(
            select(EmailProcessingLog).where(
                EmailProcessingLog.webhook_id == message_id
            )
        )
        if email_log := result.scalar_one_or_none():
            email_log.status = "failed"
            email_log.error_message = error_message
            self.db.commit()
