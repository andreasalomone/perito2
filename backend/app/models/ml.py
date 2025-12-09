import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Uuid

from app.models.base import Base


class MLTrainingPair(Base):
    """The Gold Mine: Maps Inputs -> AI Draft -> Human Final"""

    __tablename__ = "ml_training_pairs"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id = Column(Uuid, ForeignKey("cases.id"))

    ai_version_id = Column(Uuid, ForeignKey("report_versions.id"))
    final_version_id = Column(Uuid, ForeignKey("report_versions.id"))

    quality_score = Column(Float)  # Optional rating
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
