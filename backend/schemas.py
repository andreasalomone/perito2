from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from uuid import UUID

# --- BASE ---
class CaseBase(BaseModel):
    reference_code: str
    client_name: Optional[str] = None # Helper to find/create Client

class CaseCreate(CaseBase):
    pass

class CaseRead(CaseBase):
    id: UUID
    organization_id: UUID
    status: str
    created_at: datetime
    
    # We will expand this with docs later
    model_config = ConfigDict(from_attributes=True)

# --- DOCUMENTS ---
class DocumentRead(BaseModel):
    id: UUID
    filename: str
    gcs_path: str
    ai_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- VERSIONS ---
class VersionRead(BaseModel):
    id: UUID
    version_number: int
    is_final: bool
    docx_storage_path: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- COMPOSITE (The "Full View") ---
class CaseDetail(CaseRead):
    documents: List[DocumentRead] = []
    report_versions: List[VersionRead] = []

class FinalizePayload(BaseModel):
    final_docx_path: str

class DownloadVariantPayload(BaseModel):
    template_type: str # "bn" | "salomone"
