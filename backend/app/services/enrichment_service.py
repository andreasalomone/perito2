"""
Enrichment Service for ICE (Intelligent Client Enrichment) Feature

Uses Google Gemini with Search Grounding to fetch corporate details:
- Full legal name (Ragione Sociale)
- VAT number (Partita IVA)
- Registered address (Sede Legale)
- Official website
- Company logo (via Google Favicon API)
"""

import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from uuid import UUID

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.models import Client

logger = logging.getLogger(__name__)


class EnrichedClientData(BaseModel):
    """Gemini response schema for structured JSON output."""

    full_legal_name: str = Field(..., description="Official registered company name")
    vat_number: Optional[str] = Field(None, description="Italian P.IVA (11 digits)")
    address_street: Optional[str] = Field(
        None, description="Sede Legale - Street address"
    )
    city: Optional[str] = Field(None, description="City name")
    zip_code: Optional[str] = Field(None, description="Postal code (CAP)")
    province: Optional[str] = Field(
        None, description="Province code (e.g., GE, MI, RM)"
    )
    country: Optional[str] = Field(None, description="Country name")
    website: Optional[str] = Field(None, description="Official company website URL")


class EmptyResponseError(Exception):
    """Raised when Gemini returns an empty or malformed response."""

    pass


def _is_retryable_error(e: BaseException) -> bool:
    """Determines if an exception should trigger a retry."""
    # Retry empty responses (API flakiness)
    if isinstance(e, EmptyResponseError):
        return True
    # Retry malformed JSON (LLM hiccup)
    if isinstance(e, json.JSONDecodeError):
        return True
    if isinstance(e, genai_errors.ServerError):
        return True
    if isinstance(e, genai_errors.ClientError):
        # Retry on 429 Resource Exhausted
        if e.code == 429:
            return True
    return False


class EnrichmentService:
    """One-shot client enrichment using Gemini with Search Grounding."""

    def __init__(self):
        # Match existing pattern from llm_handler.py and email_ai_extractor.py
        self.client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_REGION,
        )
        self.retry_policy = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(_is_retryable_error),
            reraise=True,
        )

    @staticmethod
    def get_favicon_url(website: Optional[str]) -> Optional[str]:
        """
        Extract favicon URL using Google's Favicon API.

        Note: This is an unofficial API but widely used and reliable.
        Returns ~70 char URL like: https://www.google.com/s2/favicons?sz=128&domain=example.com
        """
        if not website:
            return None
        try:
            # Normalize URL
            url = website if website.startswith("http") else f"https://{website}"
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            if domain:
                # Remove www. prefix for cleaner favicon lookup
                domain = domain.replace("www.", "")
                return f"https://www.google.com/s2/favicons?sz=128&domain={domain}"
        except Exception:
            pass
        return None

    async def enrich_client(self, query_name: str) -> Optional[dict]:
        """
        Search web for company info, return structured data.

        Args:
            query_name: Company name to search for (e.g., "Allianz")

        Returns:
            Dict with enriched fields or None if failed
        """
        prompt = f"""
Find the official corporate details for the Italian insurance company or business: "{query_name}".

I need accurate data for a CRM system:
1. Full Legal Name (Ragione Sociale) - the exact official registered name
2. VAT Number (Partita IVA) - 11 digits for Italian companies, format: IT12345678901
3. Registered Address (Sede Legale) - street, city, postal code (CAP), province code
4. Official Website URL - the company's main domain

Search the web for accurate information. Prioritize:
- The company's official website, especially footer or "Note Legali" / "Legal" page
- Italian business registries (Camera di Commercio, Registro Imprese)
- Official company profiles on LinkedIn or similar

If you cannot find a field with high confidence, return an empty string for that field.
Do NOT make up or guess values.
"""

        try:
            async for attempt in self.retry_policy:
                with attempt:
                    response = await self.client.aio.models.generate_content(
                        model=settings.GEMINI_CLIENTS_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            response_mime_type="application/json",
                            response_schema=EnrichedClientData,
                            temperature=0.1,  # Low temp for factual accuracy
                        ),
                    )

                    # Check for empty response INSIDE retry loop
                    raw_text = response.text if hasattr(response, "text") else None
                    if not raw_text or raw_text.strip().startswith("<ctrl"):
                        # API returned empty or malformed response - retry
                        logger.warning(
                            f"Empty/malformed response for '{query_name}', retrying... "
                            f"(attempt {attempt.retry_state.attempt_number}/3)"
                        )
                        raise EmptyResponseError(f"Empty response for '{query_name}'")

                    # Parse JSON (also inside retry loop)
                    data: Dict[str, Any] = json.loads(raw_text)

                    if not isinstance(data, dict):
                        raise ValueError("Gemini response is not a JSON object")

                    # Add favicon URL derived from website
                    data["logo_url"] = self.get_favicon_url(data.get("website"))

                    logger.info(
                        f"Enriched '{query_name}': name='{data.get('full_legal_name')}', "
                        f"VAT='{data.get('vat_number')}', logo={'✓' if data.get('logo_url') else '✗'}"
                    )
                    return data

        except json.JSONDecodeError as e:
            # Should be caught by retry policy, but if it exhausts retries:
            logger.error(
                f"Failed to parse Gemini JSON response for '{query_name}' after retries: {e}"
            )
            if "raw_text" in locals():
                logger.error(
                    f"  Raw text was: '{raw_text[:100] if raw_text else '<empty>'}'"
                )
            return None
        except EmptyResponseError:
            logger.error(
                f"Enrichment failed for '{query_name}': empty response after 3 retries"
            )
            return None
        except Exception as e:
            logger.error(f"Enrichment failed for '{query_name}': {e}", exc_info=True)
            return None

        return None

    async def enrich_and_update_client(
        self, client_id: str, original_name: str, db: Session
    ) -> bool:
        """
        Full enrichment flow: fetch data from Gemini, update DB record.

        Production safeguards:
        - UniqueConstraint check before name update
        - RLS context for Postgres
        - Graceful failure (returns False, never raises)

        Args:
            client_id: UUID of the client to update
            original_name: Original name used for Gemini search
            db: SQLAlchemy session

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            enriched = await self.enrich_client(original_name)
            if not enriched:
                return False

            client = db.get(Client, UUID(client_id))
            if not client:
                logger.warning(f"Client {client_id} not found (may have been deleted)")
                return False

            # Set RLS context for Postgres (Edge Case 9)
            db.execute(
                text("SELECT set_config('app.current_org_id', :oid, false)"),
                {"oid": str(client.organization_id)},
            )

            # Update name with UniqueConstraint guard (Edge Case 1)
            if enriched.get("full_legal_name"):
                new_name = enriched["full_legal_name"]
                # Check if name would cause conflict with another client
                existing = (
                    db.query(Client)
                    .filter(
                        Client.organization_id == client.organization_id,
                        Client.name == new_name,
                        Client.id != client.id,
                    )
                    .first()
                )
                if not existing:
                    client.name = new_name
                else:
                    logger.warning(
                        f"Skipping name update: '{new_name}' already exists for org {client.organization_id}"
                    )

            # Update other fields (only if non-empty)
            if enriched.get("vat_number"):
                client.vat_number = enriched["vat_number"]
            if enriched.get("address_street"):
                client.address_street = enriched["address_street"]
            if enriched.get("city"):
                client.city = enriched["city"]
            if enriched.get("zip_code"):
                client.zip_code = enriched["zip_code"]
            if enriched.get("province"):
                client.province = enriched["province"]
            if enriched.get("country"):
                client.country = enriched["country"]
            if enriched.get("website"):
                client.website = enriched["website"]
            if enriched.get("logo_url"):
                client.logo_url = enriched["logo_url"]

            db.commit()
            logger.info(
                f"Updated client {client_id} with enriched data: "
                f"name='{client.name}', VAT='{client.vat_number}'"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update client {client_id}: {e}", exc_info=True)
            db.rollback()
            return False
