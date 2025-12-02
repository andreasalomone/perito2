from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

# --- ENUMS ---
class AIStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class CaseStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"

# --- BASE ---
class CaseBase(BaseModel):
    reference_code: str
    client_name: Optional[str] = None # Helper to find/create Client

class CaseCreate(CaseBase):
    pass

class CaseSummary(CaseBase):
    id: UUID
    organization_id: UUID
    status: CaseStatus
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- DOCUMENTS ---
class DocumentRead(BaseModel):
    id: UUID
    filename: str
    ai_status: AIStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

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
