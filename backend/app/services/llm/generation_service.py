"""Generation service for LLM API calls with retry and fallback logic."""

import asyncio
import logging
from typing import List, Optional, Union

import httpx
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Constants & Configuration
# -----------------------------------------------------------------------------

# Exceptions that warrant a retry attempt
RETRIABLE_EXCEPTIONS = (
    google_exceptions.RetryError,
    google_exceptions.ServiceUnavailable,
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
    google_exceptions.Aborted,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    asyncio.TimeoutError,  # explicit inclusion for the wait_for wrapper
)

# Safety settings optimized for Insurance/Legal context.
# We explicitly allow "Dangerous Content" because accident reports
# naturally contain descriptions of danger, destruction, and injury.
# Blocking these would break the core functionality.
INSURANCE_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    ),
]

# -----------------------------------------------------------------------------
# Service Logic
# -----------------------------------------------------------------------------


def build_generation_config(cache_name: Optional[str]) -> types.GenerateContentConfig:
    """
    Builds the configuration object for the Gemini API.

    Args:
        cache_name: The resource name of the cached content (if any).

    Returns:
        A strictly typed GenerateContentConfig object.
    """
    config_args = {
        "max_output_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
        "safety_settings": INSURANCE_SAFETY_SETTINGS,
        "response_mime_type": "application/json",  # Force JSON for programmatic parsing
    }

    if cache_name:
        config_args["cached_content"] = cache_name
        logger.info("Configuration set to use Context Cache: %s", cache_name)
    else:
        logger.info("Configuration set for standard generation (No Cache).")

    return types.GenerateContentConfig(**config_args)


async def generate_with_retry(
    client: genai.Client,
    model: str,
    contents: List[Union[str, types.Part, types.File]],
    config: types.GenerateContentConfig,
) -> types.GenerateContentResponse:
    """
    Executes the LLM generation request with exponential backoff and timeouts.

    Args:
        client: The initialized Gemini API client.
        model: The model identifier (e.g., 'gemini-1.5-pro').
        contents: The prompt payload (text, files, parts).
        config: The generation settings.

    Returns:
        The raw response object from the API.

    Raises:
        tenacity.RetryError: If the maximum number of attempts is reached.
    """
    retry_strategy = AsyncRetrying(
        stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
        # Exponential backoff: 2s, 4s, 8s... up to 10s max.
        # This prevents 'thundering herd' on the API.
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RETRIABLE_EXCEPTIONS),
        reraise=True,
    )

    async for attempt in retry_strategy:
        with attempt:
            try:
                logger.debug(
                    "Attempt %d: Calling Gemini generate_content...",
                    attempt.retry_state.attempt_number,
                )

                # We enforce a client-side hard timeout using asyncio.wait_for
                # because the library's internal timeout isn't always reliable
                # for hanging TCP connections.
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=settings.LLM_API_TIMEOUT_SECONDS,
                )
                return response

            except RETRIABLE_EXCEPTIONS as e:
                logger.warning(
                    "LLM Generation Attempt %d failed: %s. Retrying...",
                    attempt.retry_state.attempt_number,
                    str(e),
                )
                raise e


