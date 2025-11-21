"""Cache service for managing Gemini API prompt caching."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from core.config import settings
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


def _get_cache_state_file_path() -> str:
    """Returns the absolute path to the cache state file."""
    # Assuming settings.CACHE_STATE_FILE is relative to the project root
    # Adjust if needed based on where the app is run from
    return os.path.abspath(settings.CACHE_STATE_FILE)


def _load_cache_name_from_state() -> Optional[str]:
    """Loads the cache name from the local state file."""
    file_path = _get_cache_state_file_path()
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            return data.get("cache_name")
    except Exception as e:
        logger.warning(f"Failed to load cache state from {file_path}: {e}")
        return None


def _save_cache_name_to_state(cache_name: str):
    """Saves the cache name to the local state file."""
    file_path = _get_cache_state_file_path()
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(
                {
                    "cache_name": cache_name,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
            )
        logger.info(f"Saved cache name {cache_name} to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save cache state to {file_path}: {e}")


def get_or_create_prompt_cache(client: genai.Client) -> Optional[str]:
    """Retrieves an existing prompt cache or creates a new one.

    Checks for a cache name in the local state file first, then settings.
    If found, tries to retrieve it and check for expiration.
    If not found, expired, or invalid, creates a new cache with predefined prompts
    and updates the local state file.

    Args:
        client: The Gemini API client.

    Returns:
        Optional[str]: The name of the active cache, or None if an error occurs.
    """
    # 1. Check local state file first
    existing_cache_name = _load_cache_name_from_state()

    # 2. Fallback to settings if not in state file
    if not existing_cache_name:
        existing_cache_name = settings.REPORT_PROMPT_CACHE_NAME

    active_cache_name: Optional[str] = None

    if existing_cache_name:
        logger.info(f"Attempting to retrieve existing cache: {existing_cache_name}")
        try:
            # Ensure the cache name has the correct prefix for retrieval
            cache_name_for_get = existing_cache_name
            if not existing_cache_name.startswith("cachedContents/"):
                cache_name_for_get = f"cachedContents/{existing_cache_name}"

            @retry(
                stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
                wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
                retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
                reraise=True,
            )
            def _get_cache_with_retry():
                return client.caches.get(name=cache_name_for_get)

            cache = _get_cache_with_retry()

            # Check expiration
            # The client library object might have expire_time as a datetime or string
            # We'll assume it's usable or we can check if it's valid
            # Actually, if get() succeeds, it's likely valid, but we should check TTL if possible
            # For now, we rely on the fact that get() returns it.

            logger.info(
                f"Retrieved cache: {cache.name}, model: {cache.model}, expires_time: {getattr(cache, 'expire_time', 'unknown')}"
            )

            # Basic validation: check if it's for the same model
            if cache.model.endswith(settings.LLM_MODEL_NAME):
                # Check if expired (if expire_time is available and in the past)
                expire_time = getattr(cache, "expire_time", None)
                is_expired = False
                if expire_time:
                    # If it's a string, parse it? Or if it's a datetime
                    # Usually google-genai returns datetime
                    now = datetime.now(timezone.utc)
                    if isinstance(expire_time, datetime) and expire_time < now:
                        is_expired = True
                    # If it's close to expiring (e.g. < 1 hour), maybe treat as expired?
                    # For now, strict expiration.

                if not is_expired:
                    logger.info(
                        f"Successfully retrieved and validated existing cache: {cache.name}"
                    )
                    active_cache_name = cache.name
                else:
                    logger.warning(
                        f"Existing cache {existing_cache_name} is expired. Will create a new one."
                    )

            else:
                logger.warning(
                    f"Existing cache {existing_cache_name} is for a different model ({cache.model}) than expected ({settings.LLM_MODEL_NAME}). "
                    f"Will create a new cache for {settings.LLM_MODEL_NAME}."
                )
        except google_exceptions.NotFound:
            logger.warning(
                f"Existing cache {existing_cache_name} not found (404). Will create a new one."
            )
        except RetryError as re:
            logger.error(
                f"Failed to retrieve cache {existing_cache_name} after multiple retries: {re}. Will attempt to create a new one.",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Error retrieving cache {existing_cache_name}: {e}. Will attempt to create a new one.",
                exc_info=True,
            )

    if not active_cache_name:
        logger.info(f"Creating new prompt cache for model: {settings.LLM_MODEL_NAME}")
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

            # Ensure model name for cache creation is just the model ID
            model_id_for_creation = settings.LLM_MODEL_NAME
            if model_id_for_creation.startswith("models/"):
                model_id_for_creation = model_id_for_creation.split("/")[-1]

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
                        "display_name": settings.CACHE_DISPLAY_NAME,
                    },
                )

            new_cache = _create_cache_with_retry()
            active_cache_name = new_cache.name
            logger.info(
                f"Successfully created new cache: {active_cache_name} with TTL: {ttl_string}"
            )

            # Prepare the cache name for logging and saving
            log_cache_name = active_cache_name.replace("cachedContents/", "")

            # Save to state file
            _save_cache_name_to_state(log_cache_name)

            logger.info(
                f'Cache name "{log_cache_name}" saved to state file. Future runs will attempt to reuse it.'
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
