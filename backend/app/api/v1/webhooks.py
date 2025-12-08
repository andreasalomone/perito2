"""
Webhooks API Router

Handles inbound webhooks from external services (e.g., Brevo email).
"""
import hashlib
import hmac
import logging
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.config import settings
from app.db.database import SessionLocal
from app.schemas.email_intake import BrevoInboundWebhook, WebhookAcceptedResponse
from app.services.email_intake_service import EmailIntakeService


logger = logging.getLogger(__name__)

router = APIRouter()


def verify_brevo_signature(payload_body: bytes, signature: str) -> bool:
    """
    Verify Brevo webhook signature using HMAC-SHA256.
    
    Brevo signs webhooks with the secret configured in their dashboard.
    """
    if not settings.BREVO_WEBHOOK_SECRET:
        logger.warning("BREVO_WEBHOOK_SECRET not configured, skipping signature check")
        return True  # Allow in development if not configured
    
    if not signature:
        return False
    
    expected = hmac.new(
        settings.BREVO_WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def process_email_background(payload_dict: Dict, db_session_factory):
    """
    Background task for email processing.
    
    Creates its own DB session to avoid session sharing issues.
    """
    # Create fresh DB session for background task
    db = db_session_factory()
    try:
        payload = BrevoInboundWebhook.model_validate(payload_dict)
        service = EmailIntakeService(db)
        result = service.process_inbound_email(payload)
        logger.info(f"Email processed in background: {result}")
    except Exception as e:
        logger.error(f"Email processing failed: {e}", exc_info=True)
    finally:
        db.close()


@router.post(
    "/brevo-inbound",
    response_model=WebhookAcceptedResponse,
    summary="Brevo Inbound Email Webhook",
    description="Receives inbound emails forwarded to sinistri@perito.my via Brevo."
)
async def brevo_inbound_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Brevo webhook endpoint - processes inbound emails.
    
    Called by Brevo when an email arrives at sinistri@perito.my.
    Responds quickly (< 5s) and processes in background.
    """
    # 1. Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("X-Brevo-Signature", "")
    
    # 2. Verify signature
    if not verify_brevo_signature(body, signature):
        logger.warning("Invalid Brevo webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 3. Parse JSON payload
    try:
        payload_dict = await request.json()
        payload = BrevoInboundWebhook.model_validate(payload_dict)
    except Exception as e:
        logger.error(f"Failed to parse Brevo payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload format")
    
    # Get first email from items array
    email_item = payload.first_email
    if not email_item:
        logger.warning("Received empty webhook payload")
        raise HTTPException(status_code=400, detail="Empty items array")
    
    message_id = email_item.MessageId
    logger.info(f"Received Brevo webhook: message_id={message_id} from={email_item.sender_email}")
    
    # 4. Process in background (respond quickly to Brevo)
    # SessionLocal is already imported at top of file
    background_tasks.add_task(
        process_email_background,
        payload_dict=payload_dict,
        db_session_factory=SessionLocal
    )
    
    # 5. Return 200 immediately
    return WebhookAcceptedResponse(
        status="accepted",
        message_id=message_id
    )


@router.get(
    "/brevo-inbound/health",
    summary="Webhook Health Check"
)
async def webhook_health():
    """Health check for webhook endpoint."""
    return {"status": "healthy", "endpoint": "brevo-inbound"}
