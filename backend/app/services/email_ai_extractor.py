"""
Email AI Extractor Service

Uses Gemini Flash-Lite to extract structured case data from inbound emails.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Schema for LLM to output
CASE_EXTRACTION_SCHEMA = """
Extract the following fields from this email. Return JSON only, no markdown.
If a field cannot be determined, use null.

{
  "reference_code": "string - case/claim reference number",
  "ns_rif": "integer - internal reference number",
  "polizza": "string - policy number",
  "tipo_perizia": "string - type of survey/assessment",
  "merce": "string - goods description short",
  "descrizione_merce": "string - detailed goods description",
  "riserva": "number - reserve amount",
  "importo_liquidato": "number - settled amount",
  "perito": "string - surveyor name",
  "cliente": "string - client/insurance company name",
  "rif_cliente": "string - client reference",
  "gestore": "string - manager name",
  "assicurato": "string - insured party name",
  "riferimento_assicurato": "string - insured reference",
  "mittenti": "string - senders",
  "broker": "string - broker name",
  "riferimento_broker": "string - broker reference",
  "destinatari": "string - recipients",
  "mezzo_di_trasporto": "string - transport means",
  "descrizione_mezzo_di_trasporto": "string - transport description",
  "luogo_intervento": "string - intervention location",
  "genere_lavorazione": "string - processing type",
  "data_sinistro": "string - incident date (YYYY-MM-DD)",
  "data_incarico": "string - assignment date (YYYY-MM-DD)",
  "note": "string - additional notes"
}
"""


@dataclass
class CaseExtractionResult:
    """Result from AI extraction."""

    reference_code: Optional[str] = None
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
    assicurato: Optional[str] = None
    riferimento_assicurato: Optional[str] = None
    mittenti: Optional[str] = None
    broker: Optional[str] = None
    riferimento_broker: Optional[str] = None
    destinatari: Optional[str] = None
    mezzo_di_trasporto: Optional[str] = None
    descrizione_mezzo_di_trasporto: Optional[str] = None
    luogo_intervento: Optional[str] = None
    genere_lavorazione: Optional[str] = None
    data_sinistro: Optional[date] = None
    data_incarico: Optional[date] = None
    note: Optional[str] = None

    # Metadata
    raw_response: Optional[str] = field(default=None, repr=False)
    extraction_success: bool = True
    error_message: Optional[str] = None


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _parse_decimal(value: Any) -> Optional[Decimal]:
    """Parse numeric value to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        return None


def _parse_int(value: Any) -> Optional[int]:
    """Parse value to int safely."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# Maximum text content size to prevent context overload
_MAX_TEXT_CONTENT_SIZE = 500_000


def _process_text_attachment(att: Dict[str, Any], idx: int) -> str:
    """Process a text attachment and return formatted content for the prompt."""
    content = att.get("content", "")

    # Truncate massive text files to prevent context overload/timeouts
    if len(content) > _MAX_TEXT_CONTENT_SIZE:
        content = content[:_MAX_TEXT_CONTENT_SIZE] + "\n...[TRUNCATED]..."

    filename = att.get("source_file", f"attachment_{idx}")
    return f"\n[DOCUMENT: {filename}]\n{content}\n"


def _process_vision_attachment(
    att: Dict[str, Any],
    client: genai.Client,
    uploaded_files: list[str],
) -> Optional[types.Part]:
    """
    Process a vision attachment by uploading to Gemini File API.

    Returns a Part for the model contents, or None if upload fails.
    """
    path = att.get("path")
    if not path:
        return None

    try:
        uploaded_file = client.files.upload(path=path)
        logger.info(
            f"Uploaded attachment {path} to Gemini File API: {uploaded_file.name}"
        )
        uploaded_files.append(uploaded_file.name)
        return types.Part.from_uri(
            file_uri=uploaded_file.uri,
            mime_type=uploaded_file.mime_type,
        )
    except Exception as upload_err:
        logger.warning(f"Failed to upload vision attachment {path}: {upload_err}")
        return None


def _process_attachments(
    attachments: list[Dict[str, Any]],
    client: genai.Client,
    uploaded_files: list[str],
) -> tuple[str, list[types.Part]]:
    """
    Process all attachments and return prompt text additions and model content parts.

    Args:
        attachments: List of attachment dicts
        client: Gemini client for file uploads
        uploaded_files: List to track uploaded file names (mutated in place)

    Returns:
        Tuple of (prompt text to append, list of vision Parts)
    """
    prompt_additions = "\n\n--- ATTACHED DOCUMENTS CONTENT ---\n"
    vision_parts: list[types.Part] = []

    for idx, att in enumerate(attachments):
        att_type = att.get("type", "text")

        if att_type == "text":
            prompt_additions += _process_text_attachment(att, idx)
        elif att_type == "vision":
            if part := _process_vision_attachment(att, client, uploaded_files):
                vision_parts.append(part)

    return prompt_additions, vision_parts


def _clean_response_text(response_text: str) -> str:
    """Remove markdown code blocks from LLM response if present."""
    if not response_text.startswith("```"):
        return response_text

    response_text = response_text.split("```")[1]
    if response_text.startswith("json"):
        response_text = response_text[4:]
    return response_text


def _parse_response_to_result(response_text: str) -> CaseExtractionResult:
    """Parse the JSON response into a CaseExtractionResult."""
    data = json.loads(response_text)

    return CaseExtractionResult(
        reference_code=data.get("reference_code"),
        ns_rif=_parse_int(data.get("ns_rif")),
        polizza=data.get("polizza"),
        tipo_perizia=data.get("tipo_perizia"),
        merce=data.get("merce"),
        descrizione_merce=data.get("descrizione_merce"),
        riserva=_parse_decimal(data.get("riserva")),
        importo_liquidato=_parse_decimal(data.get("importo_liquidato")),
        perito=data.get("perito"),
        cliente=data.get("cliente"),
        rif_cliente=data.get("rif_cliente"),
        gestore=data.get("gestore"),
        assicurato=data.get("assicurato"),
        riferimento_assicurato=data.get("riferimento_assicurato"),
        mittenti=data.get("mittenti"),
        broker=data.get("broker"),
        riferimento_broker=data.get("riferimento_broker"),
        destinatari=data.get("destinatari"),
        mezzo_di_trasporto=data.get("mezzo_di_trasporto"),
        descrizione_mezzo_di_trasporto=data.get("descrizione_mezzo_di_trasporto"),
        luogo_intervento=data.get("luogo_intervento"),
        genere_lavorazione=data.get("genere_lavorazione"),
        data_sinistro=_parse_date(data.get("data_sinistro")),
        data_incarico=_parse_date(data.get("data_incarico")),
        note=data.get("note"),
        raw_response=response_text,
        extraction_success=True,
    )


def _cleanup_uploaded_files(client: genai.Client, file_names: list[str]) -> None:
    """Delete uploaded files from Gemini to prevent accumulation/quota issues."""
    if not file_names:
        return

    logger.info(f"Cleaning up {len(file_names)} temporary Gemini files...")
    for fname in file_names:
        try:
            client.files.delete(name=fname)
            logger.debug(f"Deleted Gemini file: {fname}")
        except Exception as cleanup_err:
            logger.warning(f"Failed to delete Gemini file {fname}: {cleanup_err}")


def _build_prompt(
    email_body: str,
    subject: Optional[str],
    sender_email: Optional[str],
) -> str:
    """Build the initial prompt text for case extraction."""
    return f"""You are an insurance case data extractor. Analyze this email and any attached documents to extract structured data.

EMAIL SUBJECT: {subject or 'N/A'}
SENDER: {sender_email or 'N/A'}

EMAIL BODY:
{email_body or 'N/A'}
"""


def _create_gemini_client() -> Optional[genai.Client]:
    """Create and return a Gemini client, or None on failure."""
    try:
        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_REGION,
        )
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None


def extract_case_data(
    email_body: str,
    subject: Optional[str] = None,
    sender_email: Optional[str] = None,
    attachments: Optional[list[Dict[str, Any]]] = None,
) -> CaseExtractionResult:
    """
    Extract structured case data from email using Gemini Flash-Lite.

    Args:
        email_body: The email body text (markdown preferred)
        subject: Email subject line
        sender_email: Sender's email address
        attachments: List of processed attachment dicts (from document_processor)

    Returns:
        CaseExtractionResult with extracted fields
    """
    if not email_body and not subject and not attachments:
        return CaseExtractionResult(
            extraction_success=False, error_message="No content to extract from"
        )

    client = _create_gemini_client()
    if client is None:
        return CaseExtractionResult(
            extraction_success=False, error_message="Failed to initialize Gemini client"
        )

    prompt_text = _build_prompt(email_body, subject, sender_email)
    model_contents: list[types.Part] = []
    uploaded_files: list[str] = []

    try:
        # Process attachments if present
        if attachments:
            att_prompt, vision_parts = _process_attachments(
                attachments, client, uploaded_files
            )
            prompt_text += att_prompt
            model_contents.extend(vision_parts)

        # Add the text prompt as the final part
        prompt_text += f"""
---

{CASE_EXTRACTION_SCHEMA}

Return ONLY valid JSON, no explanation or markdown code blocks.
"""
        model_contents.append(types.Part.from_text(text=prompt_text))

        # Call the model
        response = client.models.generate_content(
            model=settings.LLM_SUMMARY_MODEL_NAME,
            contents=model_contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2000,
                response_mime_type="application/json",
            ),
        )

        # Parse and return result
        response_text = _clean_response_text(response.text.strip())
        result = _parse_response_to_result(response_text)
        logger.info(
            f"Extracted case data: ref={result.reference_code}, cliente={result.cliente}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        return CaseExtractionResult(
            extraction_success=False, error_message=f"JSON parse error: {e}"
        )
    except Exception as e:
        logger.error(f"AI extraction failed: {e}", exc_info=True)
        return CaseExtractionResult(extraction_success=False, error_message=str(e))
    finally:
        _cleanup_uploaded_files(client, uploaded_files)
