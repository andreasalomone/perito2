import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Import the Async Session Factory
from app.db.database import AsyncSessionLocal
from app.models.outbox import OutboxMessage
from app.services import report_generation_service

logger = logging.getLogger(__name__)


async def process_message(message_id, db: AsyncSession):
    """
    Process a single message using an AsyncSession.
    Refactored to purely use AsyncSession for compatibility with case_service.py calls.
    """
    # Use 'execute' + 'scalars' for Async compatibility
    result = await db.execute(
        select(OutboxMessage).filter(OutboxMessage.id == message_id)
    )
    msg = result.scalars().first()

    if not msg or msg.status != "PENDING":
        return

    try:
        if msg.topic == "generate_report":
            await report_generation_service.trigger_generation_task(
                case_id=msg.payload["case_id"],
                organization_id=msg.payload["organization_id"],
            )

        msg.status = "PROCESSED"
        msg.processed_at = datetime.now(timezone.utc)
        await db.commit()

    except Exception as e:
        logger.error(f"Failed to process outbox message {message_id}: {e}")
        msg.retry_count += 1
        msg.error_log = str(e)
        await db.commit()
        raise e


async def process_outbox_batch_async(db: AsyncSession, batch_size: int = 10):
    """
    Fully async version for async contexts (FastAPI endpoints, async tasks).
    Reads PENDING messages with row locking and processes them.

    This version should be used when calling from async code to avoid
    RuntimeError: asyncio.run() cannot be called from a running event loop.
    """
    # 1. Fetch pending messages with row locking (Async)
    result = await db.execute(
        select(OutboxMessage)
        .filter(OutboxMessage.status == "PENDING")
        .order_by(OutboxMessage.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )
    messages = result.scalars().all()

    if not messages:
        return

    # 2. Process each message
    for msg in messages:
        try:
            await process_message(msg.id, db)
        except Exception as e:
            logger.error(f"Batch processing error for {msg.id}: {e}")
            # Individual error handling is done inside process_message


def process_outbox_batch(db: Session, batch_size: int = 10):
    """
    SYNC wrapper for backwards compatibility with cron jobs.
    Creates a new event loop for async operations.

    NOTE: Do NOT call from async contexts. Use process_outbox_batch_async instead.
    """
    # FIX BUG-2: Check if we're in an existing event loop
    # FIX BUG-2: Check if we're in an existing event loop
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # We are in an async context (e.g. FastAPI). We CANNOT use asyncio.run().
            # Schedule the work on the existing loop (Fire-and-forget).
            logger.warning(
                "process_outbox_batch called from async context. Scheduling background task."
            )
            loop.create_task(
                process_outbox_batch_async(AsyncSessionLocal(), batch_size)
            )
            return
    except RuntimeError:
        # No event loop running, safe to proceed with asyncio.run()
        pass
    # 1. Fetch pending messages with row locking (Sync)
    messages = (
        db.query(OutboxMessage)
        .filter(OutboxMessage.status == "PENDING")
        .order_by(OutboxMessage.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(batch_size)
        .all()
    )

    if not messages:
        return

    # 2. Extract IDs to pass across the Sync/Async boundary
    # We do NOT pass the 'messages' ORM objects because they are bound to the Sync session.
    msg_ids = [msg.id for msg in messages]

    async def _process_batch_async():
        # 3. Create a FRESH Async Session for the worker logic
        async with AsyncSessionLocal() as async_db:
            for msg_id in msg_ids:
                try:
                    await process_message(msg_id, async_db)
                except Exception as e:
                    logger.error(f"Batch processing error for {msg_id}: {e}")
                    # Individual error handling is done inside process_message

    # 4. Bridge the gap
    asyncio.run(_process_batch_async())
