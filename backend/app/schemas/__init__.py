from pydantic import BaseModel, ConfigDict, model_validator
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
    client_name: Optional[str] = None  # Will be populated from ORM relationship
    
    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode='before')
    @classmethod
    def extract_client_name(cls, data: Any) -> Any:
        """Extract client_name from the ORM Case.client relationship."""
        # Handle ORM object
        if not isinstance(data, dict):
            # This is an ORM object, check for client relationship
            client_name = None
            if hasattr(data, 'client') and data.client:
                client_name = data.client.name
            
            # Create a dict with all ORM attributes plus the flattened client_name
            # WARNING: If you add fields to CaseSummary, you MUST add them here too!
            data_dict = {
                'id': data.id,
                'organization_id': data.organization_id,
                'reference_code': data.reference_code,
                'status': data.status,
                'created_at': data.created_at,
                'client_name': client_name
            }

            # FIX: If the target model (cls) has these fields, we must include them
            # otherwise they get stripped by this manual dict construction.
            if 'documents' in cls.model_fields:
                data_dict['documents'] = getattr(data, 'documents', [])
            
            if 'report_versions' in cls.model_fields:
                data_dict['report_versions'] = getattr(data, 'report_versions', [])
            return data_dict
        return data



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
