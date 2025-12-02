"""Cache service for managing Gemini API prompt caching."""


import logging
import os
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types, errors
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from config import settings
from core.prompt_config import (
    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI,
    SCHEMA_REPORT,
    SYSTEM_INSTRUCTION,
)

logger = logging.getLogger(__name__)

RETRIABLE_GEMINI_EXCEPTIONS = (
    google_exceptions.RetryError,
    google_exceptions.ServiceUnavailable,
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
    google_exceptions.Aborted,
)





def get_or_create_prompt_cache(client: genai.Client) -> Optional[str]:
    """Retrieves an existing prompt cache or creates a new one.

    Queries the Gemini API for a cache with the configured display name.
    If found and valid (not expired), returns it.
    Otherwise, creates a new cache.

    Args:
        client: The Gemini API client.

    Returns:
        Optional[str]: The name of the active cache, or None if an error occurs.
    """
    display_name = settings.CACHE_DISPLAY_NAME
    model_name = settings.LLM_MODEL_NAME
    
    # Ensure model name for cache creation is just the model ID
    model_id_for_creation = model_name
    if model_id_for_creation.startswith("models/"):
        model_id_for_creation = model_id_for_creation.split("/")[-1]

    active_cache_name: Optional[str] = None

    logger.info(f"Looking for existing cache with display_name: {display_name} for model: {model_name}")

    try:
        # List caches and find match
        # Note: client.caches.list() returns an iterable
        @retry(
            stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
            wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
            retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
            reraise=True,
        )
        def _list_caches_with_retry():
            return list(client.caches.list())

        caches = _list_caches_with_retry()
        
        for cache in caches:
            # Check if display name matches and model matches
            # Note: cache.model might be full resource name "models/gemini-..."
            if (getattr(cache, 'display_name', '') == display_name and 
                (cache.model == model_name or cache.model.endswith(f"/{model_id_for_creation}"))):
                
                # Check expiration
                expire_time = getattr(cache, "expire_time", None)
                is_expired = False
                if expire_time:
                    now = datetime.now(timezone.utc)
                    if isinstance(expire_time, datetime) and expire_time < now:
                        is_expired = True
                
                if not is_expired:
                    logger.info(f"Found valid existing cache: {cache.name}")
                    active_cache_name = cache.name
                    break
                else:
                    logger.info(f"Found expired cache: {cache.name}. Ignoring.")

    except Exception as e:
        logger.warning(f"Failed to list caches: {e}. Proceeding to create new one.")

    if not active_cache_name:
        logger.info(f"Creating new prompt cache for model: {model_name}")
        try:
            # Define content parts with roles
            cached_content_parts = [
                types.Content(
                    parts=[types.Part(text=GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI)],
                    role="user",
                ),
                types.Content(parts=[types.Part(text=SCHEMA_REPORT)], role="user"),
            ]

            ttl_seconds = settings.CACHE_TTL_DAYS * 24 * 60 * 60
            ttl_string = f"{ttl_seconds}s"

            @retry(
                stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
                wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
                retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
                reraise=True,
            )
            def _create_cache_with_retry():
                return client.caches.create(
                    model=model_id_for_creation,
                    config={
                        "contents": cached_content_parts,
                        "system_instruction": types.Content(
                            parts=[types.Part(text=SYSTEM_INSTRUCTION)], role="system"
                        ),
                        "ttl": ttl_string,
                        "display_name": display_name,
                    },
                )

            new_cache = _create_cache_with_retry()
            active_cache_name = new_cache.name
            logger.info(
                f"Successfully created new cache: {active_cache_name} with TTL: {ttl_string}"
            )

        except RetryError as re:
            logger.error(
                f"Failed to create new prompt cache after multiple retries: {re}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(f"Failed to create new prompt cache: {e}", exc_info=True)
            return None

    return active_cache_name
