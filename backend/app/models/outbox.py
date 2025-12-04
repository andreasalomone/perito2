import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Uuid, Text, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base

class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    topic = Column(String(50), nullable=False) # e.g., "generate_report"
    payload = Column(JSONB, nullable=False) # The data needed for the task
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, PROCESSED, FAILED
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_log = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_outbox_pending_fifo', 'created_at', postgresql_where=text("status = 'PENDING'")),
    )
