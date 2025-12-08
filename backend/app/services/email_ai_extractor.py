"""
Email AI Extractor Service

Uses Gemini Flash-Lite to extract structured case data from inbound emails.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
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
  "note": "string - additional notes",
  "ai_summary": "string - brief markdown summary of the case"
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
    ai_summary: Optional[str] = None
    
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


from decimal import InvalidOperation


def extract_case_data(
    email_body: str,
    subject: Optional[str] = None,
    sender_email: Optional[str] = None,
    attachments: Optional[list[Dict[str, Any]]] = None  # New argument
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
            extraction_success=False,
            error_message="No content to extract from"
        )
    
    # Initialize prompt parts
    prompt_text = f"""You are an insurance case data extractor. Analyze this email and any attached documents to extract structured data.

EMAIL SUBJECT: {subject or 'N/A'}
SENDER: {sender_email or 'N/A'}

EMAIL BODY:
{email_body or 'N/A'}
"""

    # Create client first (needed for uploads)
    try:
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_REGION
        )
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return CaseExtractionResult(extraction_success=False, error_message=str(e))

    model_contents = []
    uploaded_files_to_cleanup = []

    try:
        # Process attachments
        if attachments:
            prompt_text += "\n\n--- ATTACHED DOCUMENTS CONTENT ---\n"
            
            for idx, att in enumerate(attachments):
                att_type = att.get("type", "text")
                
                if att_type == "text":
                    # Append text content directly to the prompt
                    content = att.get("content", "")
                    
                    # SAFETY: Truncate massive text files to prevent context overload/timeouts
                    # Gemini Flash-Lite is generous (1M tokens), but let's be reasonable (e.g. ~500k chars)
                    # to keep latency and error rates down.
                    if len(content) > 500_000:
                        content = content[:500_000] + "\n...[TRUNCATED]..."
                        
                    filename = att.get("source_file", f"attachment_{idx}")
                    prompt_text += f"\n[DOCUMENT: {filename}]\n{content}\n"
                    
                elif att_type == "vision":
                    # Upload to Gemini File API (Ephemeral)
                    path = att.get("path")
                    if path:
                        try:
                            # Upload file
                            uploaded_file = client.files.upload(path=path)
                            logger.info(f"Uploaded attachment {path} to Gemini File API: {uploaded_file.name}")
                            
                            # Track for cleanup
                            uploaded_files_to_cleanup.append(uploaded_file.name)
                            
                            # Add as content part
                            model_contents.append(types.Part.from_uri(
                                file_uri=uploaded_file.uri,
                                mime_type=uploaded_file.mime_type
                            ))
                        except Exception as upload_err:
                            logger.warning(f"Failed to upload vision attachment {path}: {upload_err}")
                    
        # Add the text prompt as the final part
        prompt_text += f"""
---

{CASE_EXTRACTION_SCHEMA}

Return ONLY valid JSON, no explanation or markdown code blocks.
"""
        model_contents.append(types.Part.from_text(text=prompt_text))

        # Use the summary/extraction model (cheapest)
        response = client.models.generate_content(
            model=settings.LLM_SUMMARY_MODEL_NAME,
            contents=model_contents,
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temp for structured output
                max_output_tokens=2000,
                response_mime_type="application/json"
            )
        )
        
        # Parse response
        response_text = response.text.strip()
        
        # Clean up potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        data = json.loads(response_text)
        
        # Build result
        result = CaseExtractionResult(
            reference_code=data.get("reference_code"),
            ns_rif=int(data["ns_rif"]) if data.get("ns_rif") else None,
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
            ai_summary=data.get("ai_summary"),
            raw_response=response_text,
            extraction_success=True
        )
        
        logger.info(f"Extracted case data: ref={result.reference_code}, cliente={result.cliente}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        return CaseExtractionResult(
            extraction_success=False,
            error_message=f"JSON parse error: {e}"
        )
    except Exception as e:
        logger.error(f"AI extraction failed: {e}", exc_info=True)
        return CaseExtractionResult(
            extraction_success=False,
            error_message=str(e)
        )
    finally:
        # CLEANUP: Delete uploaded files from Gemini to prevent accumulation/quota issues
        if uploaded_files_to_cleanup:
            logger.info(f"Cleaning up {len(uploaded_files_to_cleanup)} temporary Gemini files...")
            for fname in uploaded_files_to_cleanup:
                try:
                    client.files.delete(name=fname)
                    logger.debug(f"Deleted Gemini file: {fname}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete Gemini file {fname}: {cleanup_err}")
