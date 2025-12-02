"""Generation service for LLM API calls with retry and fallback logic."""

import asyncio
import logging
from typing import Any, List, Optional, Union

import httpx
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

RETRIABLE_GEMINI_EXCEPTIONS = (
    google_exceptions.RetryError,
    google_exceptions.ServiceUnavailable,
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
    google_exceptions.Aborted,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
)


def build_generation_config(cache_name: Optional[str]) -> types.GenerateContentConfig:
    """Builds generation configuration for LLM API call.

    Args:
        cache_name: Optional cache name to use for the generation.

    Returns:
        GenerateContentConfig object with settings and optional cached content.
    """
    gen_config_dict = {
        "max_output_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
    }

    safety_settings_list = [
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
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
    ]

    generation_config_args = {
        **gen_config_dict,
        "safety_settings": safety_settings_list,
    }

    if cache_name:
        generation_config_args["cached_content"] = cache_name
        logger.info(f"Using cached content: {cache_name} for report generation.")
    else:
        logger.info("Request will NOT use cached content (prompts included directly)")

    return types.GenerateContentConfig(**generation_config_args)


async def generate_with_retry(
    client: genai.Client,
    model: str,
    contents: List[Union[str, types.Part, types.File]],
    config: types.GenerateContentConfig,
) -> Any:
    """Generates content with retry logic.

    Args:
        client: The Gemini API client.
        model: The model name to use.
        contents: List of content parts to send.
        config: Generation configuration.

    Returns:
        The LLM response object.

    Raises:
        RetryError: If all retry attempts fail.
        asyncio.TimeoutError: If the request times out.
    """
    response = None

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
        wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
        retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
        reraise=True,
    ):
        with attempt:
            logger.debug(
                f"Calling Gemini generate_content (attempt {attempt.retry_state.attempt_number})..."
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                ),
                timeout=settings.LLM_API_TIMEOUT_SECONDS,
            )

    return response


