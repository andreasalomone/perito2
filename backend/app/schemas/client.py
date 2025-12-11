from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    """Base fields for Client"""

    name: str = Field(..., max_length=255)
    vat_number: Optional[str] = Field(None, max_length=50)

    # Enrichment Fields
    logo_url: Optional[str] = Field(None, max_length=1024)
    address_street: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    zip_code: Optional[str] = Field(None, max_length=20)
    province: Optional[str] = Field(None, max_length=10)
    country: Optional[str] = Field("Italia", max_length=100)
    website: Optional[str] = Field(None, max_length=500)

    # Contact Fields
    referente: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    telefono: Optional[str] = Field(None, max_length=50)


class ClientCreate(ClientBase):
    """Schema for creating a new Client"""

    pass


class ClientUpdate(BaseModel):
    """Schema for updating an existing Client (all fields optional)"""

    name: Optional[str] = Field(None, max_length=255)
    vat_number: Optional[str] = Field(None, max_length=50)

    logo_url: Optional[str] = Field(None, max_length=1024)
    address_street: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    zip_code: Optional[str] = Field(None, max_length=20)
    province: Optional[str] = Field(None, max_length=10)
    country: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=500)

    referente: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    telefono: Optional[str] = Field(None, max_length=50)


class ClientDetail(ClientBase):
    """Full Client details for API responses"""

    id: UUID
    organization_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientListItem(BaseModel):
    """Lightweight Client representation for lists"""

    id: UUID
    name: str
    logo_url: Optional[str] = None
    city: Optional[str] = None
    case_count: int = 0

    model_config = ConfigDict(from_attributes=True)
