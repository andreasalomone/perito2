from pydantic import BaseModel, ConfigDict, computed_field, Field
from typing import List, Optional, Any
from datetime import date, datetime
from decimal import Decimal
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
    # Business fields
    ns_rif: Optional[int] = None
    polizza: Optional[str] = None
    tipo_perizia: Optional[str] = None
    merce: Optional[str] = None
    descrizione_merce: Optional[str] = None
    riserva: Optional[Decimal] = None
    importo_liquidato: Optional[Decimal] = None
    perito: Optional[str] = None
    cliente: Optional[str] = None
    rif_cliente: Optional[str] = None
    gestore: Optional[str] = None
    mezzo_di_trasporto: Optional[str] = None
    descrizione_mezzo_di_trasporto: Optional[str] = None
    luogo_intervento: Optional[str] = None
    assicurato: Optional[str] = None
    riferimento_assicurato: Optional[str] = None
    mittenti: Optional[str] = None
    broker: Optional[str] = None
    riferimento_broker: Optional[str] = None
    destinatari: Optional[str] = None
    genere_lavorazione: Optional[str] = None
    data_sinistro: Optional[date] = None
    data_incarico: Optional[date] = None
    note: Optional[str] = None
    # ai_summary REMOVED from Base to avoid bloat in List View

class CaseCreate(CaseBase):
    client_name: Optional[str] = None # Helper to find/create Client


# --- CASE UPDATE (for PATCH endpoint) ---
class CaseUpdate(BaseModel):
    """Schema for PATCH /cases/{id} - all fields optional."""
    reference_code: Optional[str] = None
    client_name: Optional[str] = None  # To update client relationship
    ns_rif: Optional[int] = None
    polizza: Optional[str] = None
    tipo_perizia: Optional[str] = None
    merce: Optional[str] = None
    descrizione_merce: Optional[str] = None
    riserva: Optional[Decimal] = None
    importo_liquidato: Optional[Decimal] = None
    perito: Optional[str] = None
    cliente: Optional[str] = None
    rif_cliente: Optional[str] = None
    gestore: Optional[str] = None
    mezzo_di_trasporto: Optional[str] = None
    descrizione_mezzo_di_trasporto: Optional[str] = None
    luogo_intervento: Optional[str] = None
    assicurato: Optional[str] = None
    riferimento_assicurato: Optional[str] = None
    mittenti: Optional[str] = None
    broker: Optional[str] = None
    riferimento_broker: Optional[str] = None
    destinatari: Optional[str] = None
    genere_lavorazione: Optional[str] = None
    data_sinistro: Optional[date] = None
    data_incarico: Optional[date] = None
    note: Optional[str] = None
    ai_summary: Optional[str] = None
    status: Optional[CaseStatus] = None

class CaseSummary(CaseBase):
    id: UUID
    organization_id: UUID
    client_id: Optional[UUID] = None  # Required by frontend for filtering
    status: CaseStatus
    created_at: datetime
    
    # Hold the client relationship during serialization but exclude from JSON output
    client: Optional[Any] = Field(default=None, exclude=True)
    
    model_config = ConfigDict(from_attributes=True)
    
    @property
    def client_name(self) -> Optional[str]:
        """
        Efficiently extracts client name from the ORM relationship.
        Using @computed_field ensures this is always included in serialization
        without manual dict construction.
        """
        if self.client:
            name: Optional[str] = self.client.name
            return name
        return None
    
    # Expose client_name via computed_field for serialization
    _computed_client_name = computed_field(return_type=Optional[str])(lambda self: self.client_name)

    @property
    def creator_email(self) -> Optional[str]:
        """
        Extracts creator email from relationship.
        """
        # Note: We access the ORM relationship 'creator' defined on the model
        # We need to ensure eager loading in the query options to avoid N+1
        if hasattr(self, 'creator') and self.creator:
            email: Optional[str] = self.creator.email
            return email
        return None
    
    # Expose creator_email via computed_field for serialization
    _computed_creator_email = computed_field(return_type=Optional[str])(lambda self: self.creator_email)



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
    ai_summary: Optional[str] = None  # Moved here from Base

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
