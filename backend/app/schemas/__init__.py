from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

# --- ENUMS ---
from app.schemas.enums import CaseStatus, ExtractionStatus


# --- DOCUMENTS ---
class DocumentRead(BaseModel):
    id: UUID
    filename: str
    ai_status: ExtractionStatus
    error_message: Optional[str] = None
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

    # Serialize Decimal as float for frontend compatibility (Zod expects number)
    model_config = ConfigDict(
        json_encoders={Decimal: lambda v: float(v) if v is not None else None}
    )


class CaseCreate(CaseBase):
    client_name: Optional[str] = None  # Helper to find/create Client
    assicurato_name: Optional[str] = None  # Helper to find/create Assicurato


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
    creator: Optional[Any] = Field(default=None, exclude=True)
    assicurato_rel: Optional[Any] = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def client_name(self) -> Optional[str]:
        """
        Efficiently extracts client name from the ORM relationship.
        Using @computed_field ensures this is always included in serialization
        without manual dict construction.
        """
        if self.client:
            name: Optional[str] = str(self.client.name) if self.client.name else None
            return name
        return None

    @computed_field
    def client_logo_url(self) -> Optional[str]:
        """
        ICE Feature: Extract client logo URL for display on case cards.
        Returns Google Favicon URL derived from client's website.
        """
        if self.client and hasattr(self.client, "logo_url"):
            logo: Optional[str] = (
                str(self.client.logo_url) if self.client.logo_url else None
            )
            return logo
        return None

    @computed_field
    def creator_email(self) -> Optional[str]:
        """
        Extracts creator email from relationship.
        """
        # Note: We access the ORM relationship 'creator' defined on the model
        # We need to ensure eager loading in the query options to avoid N+1
        if hasattr(self, "creator") and self.creator:
            email: Optional[str] = (
                str(self.creator.email) if self.creator.email else None
            )
            return email
        return None

    @computed_field
    def creator_name(self) -> Optional[str]:
        """
        Extracts creator name as "First L." format from relationship.
        """
        if hasattr(self, "creator") and self.creator:
            first = self.creator.first_name or ""
            last = self.creator.last_name or ""
            # Abbreviate last name to first letter + period
            last_initial = f"{last[0]}." if last else ""
            full_name = f"{first} {last_initial}".strip()
            return full_name if full_name else None
        return None

    @computed_field
    def assicurato_display(self) -> Optional[str]:
        """
        Returns assicurato name for display.
        Priority: assicurato_rel.name (user-selected) > assicurato (AI-extracted string)
        """
        if self.assicurato_rel and hasattr(self.assicurato_rel, "name"):
            return str(self.assicurato_rel.name)
        return None


# --- LIGHTWEIGHT LIST ITEM (Reduces payload ~85%) ---
class CaseListItem(BaseModel):
    """
    Minimal schema for GET /cases/ list endpoint.
    Only includes fields actually displayed in dashboard cards.
    """

    id: UUID
    organization_id: UUID
    client_id: Optional[UUID] = None
    reference_code: str
    status: CaseStatus
    created_at: datetime

    # Hold relationships during serialization but exclude from JSON
    client: Optional[Any] = Field(default=None, exclude=True)
    creator: Optional[Any] = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def client_name(self) -> Optional[str]:
        if self.client:
            return str(self.client.name) if self.client.name else None
        return None

    @computed_field
    def client_logo_url(self) -> Optional[str]:
        if self.client and hasattr(self.client, "logo_url"):
            return str(self.client.logo_url) if self.client.logo_url else None
        return None

    @computed_field
    def creator_email(self) -> Optional[str]:
        if self.creator:
            return str(self.creator.email) if self.creator.email else None
        return None

    @computed_field
    def creator_name(self) -> Optional[str]:
        """Extracts creator name as 'First L.' format from relationship."""
        if self.creator:
            first = self.creator.first_name or ""
            last = self.creator.last_name or ""
            # Abbreviate last name to first letter + period
            last_initial = f"{last[0]}." if last else ""
            full_name = f"{first} {last_initial}".strip()
            return full_name if full_name else None
        return None


# --- VERSIONS ---
class VersionRead(BaseModel):
    id: UUID
    version_number: int
    is_final: bool
    # REMOVED: docx_storage_path (Security Risk)
    created_at: datetime
    # Google Docs Live Draft support
    is_draft_active: bool = False
    edit_link: Optional[str] = None
    source: Optional[str] = None  # 'preliminary' | 'final' | None
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
    is_generating: bool = False  # Computed field


class FinalizePayload(BaseModel):
    final_docx_path: str


class DownloadVariantPayload(BaseModel):
    template_type: str  # "bn" | "salomone"


class DocumentRegisterPayload(BaseModel):
    filename: str
    gcs_path: str
    mime_type: str


class InitiateUploadPayload(BaseModel):
    """Payload for combined upload initiation (reduces 3 requests to 2)."""

    filename: str
    content_type: str


class InitiateUploadResponse(BaseModel):
    """Response from initiate-upload with document ID and signed URL."""

    document_id: UUID
    upload_url: str
    gcs_path: str


class GeneratePayload(BaseModel):
    """Payload for report generation with language and extra instructions options."""

    # SECURITY: Use Literal to restrict to allowed values only (defense in depth)
    language: Literal["italian", "english", "spanish"] = "italian"

    # Optional extra instructions from the user (max 2000 chars for safety)
    extra_instructions: Optional[str] = Field(default=None, max_length=2000)


# --- DOCUMENT ANALYSIS ---
class DocumentAnalysisRead(BaseModel):
    """Response schema for document analysis results."""

    id: UUID
    summary: str
    received_docs: List[str]
    missing_docs: List[str]
    document_hash: str  # SHA-256 hash of document IDs for staleness detection
    is_stale: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentAnalysisResponse(BaseModel):
    """GET response for document analysis endpoint."""

    analysis: Optional[DocumentAnalysisRead] = None
    can_update: bool = True  # False if docs are still processing
    pending_docs: int = 0


class DocumentAnalysisCreateResponse(BaseModel):
    """POST response for document analysis endpoint."""

    analysis: DocumentAnalysisRead
    generated: bool = True  # False if returned cached (not stale)


class DocumentAnalysisRequest(BaseModel):
    """POST request for document analysis endpoint."""

    force: bool = False  # If true, regenerate even if not stale


# --- DOCUMENTS LIST ---
class DocumentListItem(BaseModel):
    """Schema for document list endpoint."""

    id: UUID
    filename: str
    mime_type: Optional[str] = None
    status: ExtractionStatus
    can_preview: bool = False  # True for PDF, images
    url: Optional[str] = None  # Signed URL
    model_config = ConfigDict(from_attributes=True)


class DocumentsListResponse(BaseModel):
    """Response for GET /cases/{case_id}/documents."""

    documents: List[DocumentListItem]
    total: int
    pending_extraction: int = 0


# --- PRELIMINARY REPORT ---
class PreliminaryReportRead(BaseModel):
    """Response schema for preliminary report."""

    id: UUID
    content: str  # The Markdown content (from ai_raw_output)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PreliminaryReportResponse(BaseModel):
    """GET response for preliminary report endpoint."""

    report: Optional[PreliminaryReportRead] = None
    can_generate: bool = True  # False if docs still processing
    pending_docs: int = 0


class PreliminaryReportCreateResponse(BaseModel):
    """POST response for preliminary report endpoint."""

    report: PreliminaryReportRead
    generated: bool = True  # False if returned cached


class PreliminaryReportRequest(BaseModel):
    """POST request for preliminary report endpoint."""

    force: bool = False  # If true, regenerate even if exists


# --- ASSICURATI ---
from app.schemas.assicurato import (
    AssicuratoBase,
    AssicuratoCreate,
    AssicuratoDetail,
    AssicuratoListItem,
)

# --- CLIENTS ---
from app.schemas.client import (
    ClientBase,
    ClientCreate,
    ClientDetail,
    ClientListItem,
    ClientUpdate,
)
