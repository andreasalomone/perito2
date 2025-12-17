from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssicuratoBase(BaseModel):
    """Base fields for Assicurato (insured party)"""

    name: str = Field(..., max_length=255)


class AssicuratoCreate(AssicuratoBase):
    """Schema for creating a new Assicurato"""

    pass


class AssicuratoListItem(BaseModel):
    """Lightweight Assicurato representation for lists/combobox"""

    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class AssicuratoDetail(AssicuratoBase):
    """Full Assicurato details for API responses"""

    id: UUID
    organization_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
