"""
Case Details Extractor Service

Extracts structured case metadata from finalized DOCX reports using Gemini 2.0 Flash Lite.
Follows the same patterns as email_ai_extractor.py for consistency.

Triggered after case finalization to auto-populate CaseDetailsPanel fields.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import UUID

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.models.cases import Case
from app.services.document_processor import extract_text_from_docx
from app.services.gcs_service import download_file_to_temp

logger = logging.getLogger(__name__)


# --- Pydantic Schema for LLM Structured Output ---


class CaseDetailsExtractionSchema(BaseModel):
    """Gemini response schema for structured JSON output.

    CRITICAL: Field names match Case model columns exactly.
    Exception: 'cliente' is extracted but mapped to client_id via fuzzy match.
    """

    # Dati Generali
    ns_rif: Optional[int] = Field(
        None, description="Numero di riferimento interno (es: 1234)"
    )
    reference_code: Optional[str] = Field(
        None, description="Codice riferimento pratica/sinistro"
    )
    polizza: Optional[str] = Field(None, description="Numero di polizza assicurativa")
    tipo_perizia: Optional[str] = Field(
        None, description="Tipo di perizia (es: Trasporti, Incendio, RC)"
    )
    data_sinistro: Optional[str] = Field(
        None, description="Data del sinistro (formato YYYY-MM-DD)"
    )
    data_incarico: Optional[str] = Field(
        None, description="Data dell'incarico (formato YYYY-MM-DD)"
    )

    # Economici
    riserva: Optional[float] = Field(None, description="Importo riserva in EUR")
    importo_liquidato: Optional[float] = Field(
        None, description="Importo liquidato in EUR"
    )

    # Parti Coinvolte
    cliente: Optional[str] = Field(
        None, description="Nome della compagnia assicurativa committente"
    )
    rif_cliente: Optional[str] = Field(None, description="Riferimento del cliente")
    assicurato: Optional[str] = Field(
        None, description="Nome dell'assicurato / danneggiato"
    )
    riferimento_assicurato: Optional[str] = Field(
        None, description="Riferimento dell'assicurato"
    )
    broker: Optional[str] = Field(None, description="Nome del broker")
    riferimento_broker: Optional[str] = Field(
        None, description="Riferimento del broker"
    )
    perito: Optional[str] = Field(None, description="Nome del perito")
    gestore: Optional[str] = Field(None, description="Nome del gestore della pratica")
    mittenti: Optional[str] = Field(
        None, description="Mittenti della spedizione (per sinistri trasporti)"
    )
    destinatari: Optional[str] = Field(None, description="Destinatari della spedizione")

    # Merci e Trasporti
    merce: Optional[str] = Field(None, description="Descrizione breve della merce")
    descrizione_merce: Optional[str] = Field(
        None, description="Descrizione dettagliata della merce"
    )
    mezzo_di_trasporto: Optional[str] = Field(
        None, description="Tipo di mezzo (Camion, Nave, Aereo, ecc.)"
    )
    descrizione_mezzo_di_trasporto: Optional[str] = Field(
        None, description="Descrizione del mezzo di trasporto"
    )

    # Luogo e Lavorazione
    luogo_intervento: Optional[str] = Field(
        None, description="Luogo del sopralluogo / intervento"
    )
    genere_lavorazione: Optional[str] = Field(None, description="Tipo di lavorazione")

    # Note
    note: Optional[str] = Field(
        None, description="Note aggiuntive, osservazioni del perito"
    )


# --- Dataclass for Internal Processing ---


@dataclass
class CaseDetailsExtractionResult:
    """Result from AI extraction."""

    # Direct DB Fields
    ns_rif: Optional[int] = None
    reference_code: Optional[str] = None
    polizza: Optional[str] = None
    tipo_perizia: Optional[str] = None
    data_sinistro: Optional[date] = None
    data_incarico: Optional[date] = None
    riserva: Optional[Decimal] = None
    importo_liquidato: Optional[Decimal] = None
    rif_cliente: Optional[str] = None
    assicurato: Optional[str] = None
    riferimento_assicurato: Optional[str] = None
    broker: Optional[str] = None
    riferimento_broker: Optional[str] = None
    perito: Optional[str] = None
    gestore: Optional[str] = None
    mittenti: Optional[str] = None
    destinatari: Optional[str] = None
    merce: Optional[str] = None
    descrizione_merce: Optional[str] = None
    mezzo_di_trasporto: Optional[str] = None
    descrizione_mezzo_di_trasporto: Optional[str] = None
    luogo_intervento: Optional[str] = None
    genere_lavorazione: Optional[str] = None
    note: Optional[str] = None

    # Special: requires client_matcher lookup
    cliente: Optional[str] = None  # Will be matched to client_id

    # Metadata
    raw_response: Optional[str] = field(default=None, repr=False)
    extraction_success: bool = True
    error_message: Optional[str] = None
    fields_extracted: int = 0


# --- Helper Functions ---


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse date string to date object. Handles multiple formats."""
    if not value:
        return None

    # Try ISO format first (YYYY-MM-DD)
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        pass

    # Try European format (DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY)
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]:
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue

    logger.warning(f"Could not parse date: {value}")
    return None


def _parse_decimal(value: Any) -> Optional[Decimal]:
    """Parse numeric value to Decimal. Handles European number format."""
    if value is None:
        return None
    try:
        str_val = str(value)
        # Handle European number format (1.234,56 -> 1234.56)
        if "," in str_val and "." in str_val:
            str_val = str_val.replace(".", "").replace(",", ".")
        elif "," in str_val:
            str_val = str_val.replace(",", ".")
        return Decimal(str_val).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"Could not parse decimal: {value}")
        return None


def _parse_int(value: Any) -> Optional[int]:
    """Parse value to int safely."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse int: {value}")
        return None


def _is_retryable_error(e: BaseException) -> bool:
    """Determines if an exception should trigger a retry."""
    error_str = str(e).lower()
    retryable_patterns = [
        "resource_exhausted",
        "429",
        "quota",
        "rate limit",
        "temporarily unavailable",
        "503",
        "deadline exceeded",
        "timeout",
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


def _is_docx_file(file_path: str) -> bool:
    """Check if file is a DOCX based on extension."""
    return file_path.lower().endswith((".docx", ".doc"))


EXTRACTION_PROMPT = """Sei un assistente esperto nell'analisi di perizie assicurative italiane.

Analizza attentamente il seguente documento di perizia e estrai TUTTI i dati strutturati che riesci a identificare.

**REGOLE IMPORTANTI:**
1. Estrai SOLO informazioni esplicitamente presenti nel testo
2. NON inventare o dedurre valori non presenti
3. Per i campi che non trovi, restituisci null
4. Le date devono essere in formato YYYY-MM-DD
5. Gli importi devono essere numeri decimali (es: 1234.56), senza simboli di valuta
6. Cerca in tutto il documento: intestazioni, tabelle, corpo del testo, conclusioni

**DOVE CERCARE I DATI:**
- **Dati generali**: intestazione del documento, prime righe, "Ns. Rif.", "Sinistro n.", "N° Polizza"
- **Parti coinvolte**: sezioni "Richiedente", "Assicurato", "Committente", "Mandante", intestazioni
- **Importi**: conclusioni, sezione "Quantificazione Danni", "Riserva Tecnica", "Liquidazione"
- **Trasporti**: sezioni specifiche per sinistri merci/trasporti, "Merce", "Vettore"
- **Date**: riferimenti temporali espliciti, "Data sinistro:", "Data incarico:", "Data evento"
- **Note**: osservazioni del perito, annotazioni, raccomandazioni, conclusioni

---

**DOCUMENTO DA ANALIZZARE:**

{report_text}

---

Restituisci SOLO JSON valido, nessuna spiegazione.
"""

# Maximum characters to send to LLM (prevents context overflow)
MAX_REPORT_CHARS = 100_000  # ~25k tokens

# Minimum content required for meaningful extraction
MIN_CONTENT_CHARS = 100



async def extract_case_details_from_text(
    combined_text: str,
) -> CaseDetailsExtractionResult:
    """
    Extract structured case details from concatenated document text.

    Used by Document Analysis flow to populate CaseDetailsPanel
    with extracted fields (excluding user-confirmed ones).
    """
    if not combined_text or len(combined_text.strip()) < MIN_CONTENT_CHARS:
        return CaseDetailsExtractionResult(
            extraction_success=False,
            error_message="Insufficient text for extraction"
        )

    # Use existing LLM extraction logic
    # Reuse the same helper that extract_case_details_from_docx uses internally
    # Note: _call_extraction_llm is what we'll extract out or reuse
    return await _call_extraction_llm(combined_text)


async def extract_case_details_from_docx(
    gcs_path: str,
) -> CaseDetailsExtractionResult:
    """
    Extract structured case details from a finalized DOCX report.

    Args:
        gcs_path: GCS path to the final DOCX file (e.g., "gs://bucket/reports/...")

    Returns:
        CaseDetailsExtractionResult with extracted fields
    """
    logger.info(f"Starting case details extraction from: {gcs_path}")

    # Validate file type
    if not _is_docx_file(gcs_path):
        logger.warning(f"File is not DOCX: {gcs_path}")
        return CaseDetailsExtractionResult(
            extraction_success=False,
            error_message=f"Unsupported file type (expected .docx): {gcs_path}",
        )

    # 1. Download DOCX from GCS to temp file
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = os.path.join(tmp_dir, "final_report.docx")

        try:
            download_file_to_temp(gcs_path, local_path)
        except ValueError as e:
            # Bucket validation or size limit error
            logger.error(f"Security check failed for GCS download: {e}")
            return CaseDetailsExtractionResult(
                extraction_success=False,
                error_message=f"Security validation failed: {e}",
            )
        except Exception as e:
            logger.error(f"Failed to download DOCX from GCS: {e}")
            return CaseDetailsExtractionResult(
                extraction_success=False, error_message=f"Download failed: {e}"
            )

        # 2. Extract text using existing function
        try:
            extracted_data = extract_text_from_docx(local_path)
            if not extracted_data or not extracted_data[0].get("content"):
                return CaseDetailsExtractionResult(
                    extraction_success=False,
                    error_message="No text content extracted from DOCX",
                )

            report_text = extracted_data[0]["content"]

            # Minimum content check
            if len(report_text.strip()) < MIN_CONTENT_CHARS:
                return CaseDetailsExtractionResult(
                    extraction_success=False,
                    error_message=f"Report too short ({len(report_text)} chars)",
                )

            # Truncate if too long
            if len(report_text) > MAX_REPORT_CHARS:
                report_text = report_text[:MAX_REPORT_CHARS]
                logger.warning(f"Report text truncated to {MAX_REPORT_CHARS} chars")

        except Exception as e:
            logger.error(f"Failed to extract text from DOCX: {e}")
            return CaseDetailsExtractionResult(
                extraction_success=False, error_message=f"Text extraction failed: {e}"
            )

    # 3. Call Gemini with structured output
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = EXTRACTION_PROMPT.format(report_text=report_text)

        retry_policy = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(_is_retryable_error),
            reraise=True,
        )

        async for attempt in retry_policy:
            with attempt:
                response = await client.aio.models.generate_content(
                    model=settings.GEMINI_DETAILS_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CaseDetailsExtractionSchema,
                        temperature=0.1,  # Low temp for factual accuracy
                        max_output_tokens=2000,
                    ),
                )

                if not response or not response.text:
                    logger.warning("Empty response from Gemini")
                    raise ValueError("Empty response")

                raw_text = response.text.strip()
                data = json.loads(raw_text)

                # Parse and build result
                result = CaseDetailsExtractionResult(
                    ns_rif=_parse_int(data.get("ns_rif")),
                    reference_code=data.get("reference_code"),
                    polizza=data.get("polizza"),
                    tipo_perizia=data.get("tipo_perizia"),
                    data_sinistro=_parse_date(data.get("data_sinistro")),
                    data_incarico=_parse_date(data.get("data_incarico")),
                    riserva=_parse_decimal(data.get("riserva")),
                    importo_liquidato=_parse_decimal(data.get("importo_liquidato")),
                    cliente=data.get("cliente"),  # Special - will be fuzzy matched
                    rif_cliente=data.get("rif_cliente"),
                    assicurato=data.get("assicurato"),
                    riferimento_assicurato=data.get("riferimento_assicurato"),
                    broker=data.get("broker"),
                    riferimento_broker=data.get("riferimento_broker"),
                    perito=data.get("perito"),
                    gestore=data.get("gestore"),
                    mittenti=data.get("mittenti"),
                    destinatari=data.get("destinatari"),
                    merce=data.get("merce"),
                    descrizione_merce=data.get("descrizione_merce"),
                    mezzo_di_trasporto=data.get("mezzo_di_trasporto"),
                    descrizione_mezzo_di_trasporto=data.get(
                        "descrizione_mezzo_di_trasporto"
                    ),
                    luogo_intervento=data.get("luogo_intervento"),
                    genere_lavorazione=data.get("genere_lavorazione"),
                    note=data.get("note"),
                    raw_response=raw_text,
                    extraction_success=True,
                )

                # Count non-null fields
                fields = [
                    result.ns_rif,
                    result.reference_code,
                    result.polizza,
                    result.tipo_perizia,
                    result.data_sinistro,
                    result.data_incarico,
                    result.riserva,
                    result.importo_liquidato,
                    result.cliente,
                    result.rif_cliente,
                    result.assicurato,
                    result.riferimento_assicurato,
                    result.broker,
                    result.riferimento_broker,
                    result.perito,
                    result.gestore,
                    result.mittenti,
                    result.destinatari,
                    result.merce,
                    result.descrizione_merce,
                    result.mezzo_di_trasporto,
                    result.descrizione_mezzo_di_trasporto,
                    result.luogo_intervento,
                    result.genere_lavorazione,
                    result.note,
                ]
                result.fields_extracted = sum(1 for f in fields if f is not None)

                logger.info(
                    f"Extraction successful: {result.fields_extracted}/25 fields extracted"
                )
                return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini JSON: {e}")
        return CaseDetailsExtractionResult(
            extraction_success=False, error_message=f"JSON parse error: {e}"
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        return CaseDetailsExtractionResult(
            extraction_success=False, error_message=str(e)
        )

    # Should not reach here, but satisfy type checker
    return CaseDetailsExtractionResult(
        extraction_success=False, error_message="Unexpected flow"
    )



# Fields that should NEVER be overwritten by AI extraction
# These are user-confirmed values from case creation
PROTECTED_FIELDS = frozenset({
    "reference_code",      # User enters on case creation (= Ns. Rif)
    "ns_rif",              # Should only be set if user entered reference_code
    "client_id",           # User selects from dropdown
    "assicurato_id",       # User selects from dropdown
    "assicurato",          # String field - prefer assicurato_rel from dropdown
})


async def update_case_from_extraction(
    case_id: str,
    org_id: str,
    extraction_result: CaseDetailsExtractionResult,
    db: AsyncSession,
    overwrite_existing: bool = False,
) -> int:
    """
    Update Case record with extracted details.

    Args:
        case_id: UUID of the case to update
        org_id: UUID of the organization (for client matching)
        extraction_result: The extraction result
        db: Async database session
        overwrite_existing: If True, overwrite non-null fields. If False, only fill nulls.

    Returns:
        Number of fields updated
    """
    if not extraction_result.extraction_success:
        logger.warning(f"Skipping update for case {case_id}: extraction failed")
        return 0

    # Set RLS context FIRST
    await db.execute(
        text("SELECT set_config('app.current_org_id', :oid, false)"),
        {"oid": org_id},
    )

    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()

    if not case:
        logger.error(f"Case {case_id} not found for update")
        return 0

    fields_updated = 0

    # Direct field mappings (field_name -> extracted_value)
    # NOTE: reference_code is EXCLUDED - it's a critical identifier
    direct_fields = {
        "ns_rif": extraction_result.ns_rif,
        "polizza": extraction_result.polizza,
        "tipo_perizia": extraction_result.tipo_perizia,
        "data_sinistro": extraction_result.data_sinistro,
        "data_incarico": extraction_result.data_incarico,
        "riserva": extraction_result.riserva,
        "importo_liquidato": extraction_result.importo_liquidato,
        "rif_cliente": extraction_result.rif_cliente,
        "assicurato": extraction_result.assicurato,
        "riferimento_assicurato": extraction_result.riferimento_assicurato,
        "broker": extraction_result.broker,
        "riferimento_broker": extraction_result.riferimento_broker,
        "perito": extraction_result.perito,
        "gestore": extraction_result.gestore,
        "mittenti": extraction_result.mittenti,
        "destinatari": extraction_result.destinatari,
        "merce": extraction_result.merce,
        "descrizione_merce": extraction_result.descrizione_merce,
        "mezzo_di_trasporto": extraction_result.mezzo_di_trasporto,
        "descrizione_mezzo_di_trasporto": extraction_result.descrizione_mezzo_di_trasporto,
        "luogo_intervento": extraction_result.luogo_intervento,
        "genere_lavorazione": extraction_result.genere_lavorazione,
        "note": extraction_result.note,
    }

    for field_name, new_value in direct_fields.items():
        if new_value is None:
            continue  # Skip null extracted values

        # CRITICAL: Never overwrite user-confirmed fields
        if field_name in PROTECTED_FIELDS:
            logger.debug(f"Skipping protected field: {field_name}")
            continue

        current_value = getattr(case, field_name, None)

        # Skip if field already has value and we're not overwriting
        if current_value is not None and not overwrite_existing:
            logger.debug(f"Skipping {field_name}: already has value")
            continue

        # Update field
        setattr(case, field_name, new_value)
        fields_updated += 1
        logger.debug(f"Updated {field_name}")

    # SPECIAL HANDLING: cliente -> client_id via fuzzy matching
    # ONLY if user did NOT already select a client (client_id is null)
    if extraction_result.cliente and case.client_id is None:
        try:
            from app.db.database import SessionLocal
            from app.services.client_matcher import find_or_create_client

            # client_matcher uses sync Session
            with SessionLocal() as sync_db:
                # Set RLS for sync session too
                sync_db.execute(
                    text("SELECT set_config('app.current_org_id', :oid, false)"),
                    {"oid": org_id},
                )
                client = find_or_create_client(
                    sync_db, UUID(org_id), extraction_result.cliente, threshold=0.65
                )
                if client:
                    case.client_id = client.id
                    fields_updated += 1
                    logger.info(
                        f"Matched cliente '{extraction_result.cliente}' -> client {client.id}"
                    )
                sync_db.commit()
        except Exception as e:
            logger.warning(
                f"Failed to match cliente '{extraction_result.cliente}': {e}"
            )

    if fields_updated > 0:
        await db.commit()
        logger.info(f"Updated {fields_updated} fields for case {case_id}")
    else:
        logger.info(f"No fields updated for case {case_id} (all already populated)")

    return fields_updated


# --- Sync Wrapper for Local Development ---


def run_extraction_sync(
    case_id: str,
    org_id: str,
    final_docx_path: str,
    overwrite_existing: bool = False,
) -> None:
    """
    Synchronous wrapper for running extraction in local development.
    Used by threading.Thread in finalize_case.

    CRITICAL: Creates fresh async connector inside this function because
    asyncio.run() creates a new event loop, incompatible with the global one.
    """
    import asyncio

    from app.core.config import settings

    async def _run() -> None:
        # Create fresh Cloud SQL async connector inside this event loop
        from google.cloud.sql.connector import IPTypes, create_async_connector
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        connector = await create_async_connector()

        async def getconn():
            return await connector.connect_async(
                settings.CLOUD_SQL_CONNECTION_NAME,
                "asyncpg",
                user=settings.DB_USER,
                password=settings.DB_PASS,
                db=settings.DB_NAME,
                ip_type=IPTypes.PUBLIC,
            )

        engine = create_async_engine(
            "postgresql+asyncpg://",
            async_creator=getconn,
            pool_size=1,
            max_overflow=0,
        )
        async_session = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )

        try:
            result = await extract_case_details_from_docx(final_docx_path)
            if result.extraction_success:
                async with async_session() as db:
                    await update_case_from_extraction(
                        case_id, org_id, result, db, overwrite_existing
                    )
            else:
                logger.warning(
                    f"Extraction failed for case {case_id}: {result.error_message}"
                )
        finally:
            await engine.dispose()
            await connector.close_async()

    asyncio.run(_run())
