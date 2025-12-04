from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from app.models.outbox import OutboxMessage
from app.services import report_generation_service
import logging

logger = logging.getLogger(__name__)

import asyncio

async def process_message(message_id, db: Session):
    """
    Process a single message by ID. 
    Used for immediate dispatch optimization.
    """
    # We need a fresh session or use the existing one carefully.
    # Since this is called after commit, we can use the passed DB session.
    # However, for safety, we should re-query the message to ensure it exists and lock it?
    # Actually, for immediate dispatch, we just want to run the logic.
    # But to be safe and consistent with the poller, we should probably just call the logic directly
    # and update the status.
    
    # Note: The passed 'db' session might be closed or committed. 
    # It's safer to query the message again.
    
    msg = db.query(OutboxMessage).filter(OutboxMessage.id == message_id).first()
    if not msg or msg.status != "PENDING":
        return

    try:
        if msg.topic == "generate_report":
            await report_generation_service.trigger_generation_task(
                case_id=msg.payload["case_id"],
                organization_id=msg.payload["organization_id"]
            )
        
        msg.status = "PROCESSED"
        msg.processed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to process outbox message {msg.id}: {e}")
        # We don't mark as FAILED immediately on first try, 
        # but for immediate dispatch we can just leave it as PENDING 
        # and let the poller retry it.
        # Or we can increment retry count.
        msg.retry_count += 1
        msg.error_log = str(e)
        db.commit()
        raise e

def process_outbox_batch(db: Session, batch_size: int = 10):
    """
    Reads PENDING messages and dispatches them.
    Uses 'SKIP LOCKED' to allow multiple Cloud Run instances to process safely.
    """
    # 1. Fetch pending messages with row locking
    # This prevents two workers from grabbing the same task
    messages = db.query(OutboxMessage).filter(
        OutboxMessage.status == "PENDING"
    ).order_by(
        OutboxMessage.created_at.asc()
    ).with_for_update(skip_locked=True).limit(batch_size).all()

    if not messages:
        return

    async def _process_batch_async():
        """Process all messages in a single event loop to avoid thrashing."""
        for msg in messages:
            try:
                await process_message(msg.id, db)
            except Exception as e:
                logger.error(f"Failed to process outbox message {msg.id}: {e}")
                msg.retry_count += 1
                msg.error_log = str(e)
                if msg.retry_count > 5:
                    msg.status = "FAILED"
                # Commit per message to save progress
                db.commit()
    
    # Run entire batch in a single event loop (avoids loop creation/destruction overhead)
    asyncio.run(_process_batch_async())

