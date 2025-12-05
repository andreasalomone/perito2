from pydantic import BaseModel, ConfigDict, computed_field, Field
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

# --- ENUMS ---
from app.schemas.enums import CaseStatus, ExtractionStatus

# --- DOCUMENTS ---
class DocumentRead(BaseModel):
    id: UUID
    filename: str
    ai_status: ExtractionStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- BASE ---
class CaseBase(BaseModel):
    reference_code: str

class CaseCreate(CaseBase):
    client_name: Optional[str] = None # Helper to find/create Client

class CaseSummary(CaseBase):
    id: UUID
    organization_id: UUID
    status: CaseStatus
    created_at: datetime
    
    # Hold the client relationship during serialization but exclude from JSON output
    client: Optional[Any] = Field(default=None, exclude=True)
    
    model_config = ConfigDict(from_attributes=True)
    
    @computed_field
    @property
    def client_name(self) -> Optional[str]:
        """
        Efficiently extracts client name from the ORM relationship.
        Using @computed_field ensures this is always included in serialization
        without manual dict construction.
        """
        if self.client:
            return self.client.name
        return None

    @computed_field
    @property
    def creator_email(self) -> Optional[str]:
        """
        Extracts creator email from relationship.
        """
        # Note: We access the ORM relationship 'creator' defined on the model
        # We need to ensure eager loading in the query options to avoid N+1
        if hasattr(self, 'creator') and self.creator:
            return self.creator.email
        return None



# --- VERSIONS ---
class VersionRead(BaseModel):
    id: UUID
    version_number: int
    is_final: bool
    # REMOVED: docx_storage_path (Security Risk)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- COMPOSITE (The "Full View") ---
class CaseDetail(CaseSummary):
    documents: List[DocumentRead] = []
    report_versions: List[VersionRead] = []

# --- LIGHTWEIGHT STATUS ---
class CaseStatusRead(BaseModel):
    id: UUID
    status: CaseStatus
    documents: List[DocumentRead]
    is_generating: bool = False # Computed field

class FinalizePayload(BaseModel):
    final_docx_path: str

class DownloadVariantPayload(BaseModel):
    template_type: str # "bn" | "salomone"

class DocumentRegisterPayload(BaseModel):
    filename: str
    gcs_path: str
    mime_type: str
