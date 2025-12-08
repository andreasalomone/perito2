import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.schemas.enums import CaseStatus

# Prevent circular imports for type checking only
if TYPE_CHECKING:
    from app.models.documents import Document, ReportVersion
    from app.models.users import Organization, User
    from app.models.email_intake import EmailProcessingLog


class Client(Base):
    """
    CRM Entity: Represents Insurance Companies (e.g., Generali, Allianz).
    Scoped to an Organization (Tenant).
    """
    __tablename__ = "clients"
    __table_args__ = (
        # Prevent duplicate client names within the same organization
        UniqueConstraint('organization_id', 'name', name='uq_clients_org_name'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vat_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Use timezone-aware UTC for all timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now() # Double safety: DB also defaults to NOW()
    )

    # Relationships
    # Note: explicit typing Mapped["ClassName"] enables IDE autocompletion
    organization: Mapped["Organization"] = relationship(back_populates="clients")
    cases: Mapped[List["Case"]] = relationship(back_populates="client")


class Case(Base):
    """
    The Core Container for a Claim (Sinistro).
    """
    __tablename__ = "cases"
    __table_args__ = (
        # Dashboard Optimization: Fetch by Org, Order by Date
        Index('idx_cases_dashboard', 'organization_id', text('created_at DESC')),
        # Search Optimization
        Index('idx_cases_reference', 'organization_id', 'reference_code'),
        Index('idx_cases_client', 'organization_id', 'client_id'),
        Index('idx_cases_creator', 'organization_id', 'creator_id'),
        # LOGIC FIX: Prevent duplicate reference codes in the same Org
        UniqueConstraint('organization_id', 'reference_code', name='uq_cases_org_ref'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    # Firebase UIDs are strings, usually 28-36 chars. 128 is a safe upper bound.
    creator_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("users.id"), nullable=True
    )
    
    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    status: Mapped[CaseStatus] = mapped_column(
        default=CaseStatus.OPEN,
        nullable=False
        # Native Enum handling is implied by the Type Hint in SA 2.0
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # -------------------------------------------------------------------------
    # Business Fields (Claim Details)
    # -------------------------------------------------------------------------
    
    # Reference number (internal)
    ns_rif: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Policy & Type
    polizza: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tipo_perizia: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Goods
    merce: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    descrizione_merce: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Financial
    riserva: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    importo_liquidato: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    # People & Roles
    perito: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cliente: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rif_cliente: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gestore: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assicurato: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    riferimento_assicurato: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mittenti: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    broker: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    riferimento_broker: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destinatari: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Transport
    mezzo_di_trasporto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    descrizione_mezzo_di_trasporto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Location & Processing
    luogo_intervento: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    genere_lavorazione: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Dates
    data_sinistro: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    data_incarico: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Notes
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    organization: Mapped["Organization"] = relationship(back_populates="cases")
    client: Mapped[Optional["Client"]] = relationship(back_populates="cases")
    
    # Changed 'backref' to explicit relationship. 
    # Requires 'cases = relationship("Case", back_populates="creator")' on User model.
    creator: Mapped[Optional["User"]] = relationship(back_populates="cases")
    
    documents: Mapped[List["Document"]] = relationship(
        back_populates="case", 
        cascade="all, delete-orphan"
    )
    report_versions: Mapped[List["ReportVersion"]] = relationship(
        back_populates="case", 
        cascade="all, delete-orphan"
    )
    email_logs: Mapped[List["EmailProcessingLog"]] = relationship(back_populates="case")
