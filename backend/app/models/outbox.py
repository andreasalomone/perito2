import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from app.db.database import Base

class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    topic = Column(String, nullable=False) # e.g., "generate_report"
    payload = Column(JSONB, nullable=False) # The data needed for the task
    status = Column(String, default="PENDING", nullable=False) # PENDING, PROCESSED, FAILED
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_log = Column(String, nullable=True)
