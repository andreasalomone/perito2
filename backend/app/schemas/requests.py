"""
Request Validation Schemas

Strict input validation for API endpoints.
These schemas are used directly in route handlers for type-safe request parsing.
"""

import re
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.enums import CaseStatus


class CaseCreateRequest(BaseModel):
    """
    Validates incoming case creation requests.

    Usage:
        @router.post("/", response_model=CaseDetail)
        def create_case(case_in: CaseCreateRequest, ...):
    """

    reference_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Case reference code, e.g., 'Sinistro 2024/005'",
    )
    client_name: Optional[str] = Field(
        default=None, max_length=255, description="Client name for CRM lookup/creation"
    )

    @field_validator("reference_code")
    @classmethod
    def sanitize_reference_code(cls, v: str) -> str:
        """Strip whitespace and validate characters."""
        v = v.strip()
        if not re.match(r"^[\w\s\-/\.À-ÿ]+$", v):
            raise ValueError("Reference code contains invalid characters")
        return v

    @field_validator("client_name")
    @classmethod
    def sanitize_client_name(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from client name."""
        if v:
            return v.strip()
        return v


class CasesListQuery(BaseModel):
    """
    Validates query parameters for case listing.
    """

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    search: Optional[str] = Field(default=None, max_length=200)
    client_id: Optional[UUID] = None
    status: Optional[CaseStatus] = None
    scope: Literal["all", "mine"] = "all"

    @field_validator("search")
    @classmethod
    def sanitize_search(cls, v: Optional[str]) -> Optional[str]:
        """Strip and validate search query."""
        if v:
            v = v.strip()
            if len(v) < 1:
                return None
        return v


class DocumentRegisterRequest(BaseModel):
    """
    Validates document registration after GCS upload.
    """

    filename: str = Field(..., min_length=1, max_length=255)
    gcs_path: str = Field(..., min_length=10, max_length=500)
    mime_type: str = Field(..., description="MIME type of the uploaded file")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Ensure filename has valid characters."""
        from pathlib import Path

        clean = Path(v).name
        if not re.match(r"^[a-zA-Z0-9_\-\. ]+$", clean):
            raise ValueError("Filename contains invalid characters")
        return clean

    @field_validator("gcs_path")
    @classmethod
    def validate_gcs_path(cls, v: str) -> str:
        """Basic path validation (full validation done in endpoint)."""
        if ".." in v or "~" in v:
            raise ValueError("Path contains invalid traversal characters")
        return v
