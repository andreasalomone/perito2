"""Generation service for LLM API calls with retry and fallback logic."""
import asyncio
import logging
from typing import Any, List, Optional, Union

import httpx
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import (
    AsyncRetrying,
    RetryError,
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


async def generate_with_fallback(
    client: genai.Client,
    model: str,
    contents: List[Union[str, types.Part, types.File]],
    config: types.GenerateContentConfig,
) -> Any:
    """Generates content with cache, falling back to non-cached on cache errors.

    Args:
        client: The Gemini API client.
        model: The model name to use.
        contents: List of content parts to send.
        config: Generation configuration (may include cached_content).

    Returns:
        The LLM response object.

    Raises:
        Exception: If both attempts fail.
    """
    try:
        # ATTEMPT 1: With cache (if available)
        logger.info(
            "Attempting LLM generation with current settings (including cache if configured)."
        )
        response = await generate_with_retry(client, model, contents, config)
        return response

    except genai_errors.ClientError as e:
        # This block catches non-retriable client errors from the first attempt.
        logger.warning(f"Initial LLM call failed with a non-retriable ClientError: {e}")

        # Check if this is a cache-related error
        cache_name = getattr(config, "cached_content", None)
        is_cache_error = (
            cache_name
            and "INVALID_ARGUMENT" in str(e)
            and ("400" in str(e) or (hasattr(e, "status_code") and e.status_code == 400))
        )

        if is_cache_error:
            logger.warning(
                "Cache-related INVALID_ARGUMENT error detected. Attempting fallback generation without cache."
            )

            # Rebuild config without cache and include prompts directly
            final_prompt_parts_fallback = [
                GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI,
                "\n\n",
                SCHEMA_REPORT,
                "\n\n",
                SYSTEM_INSTRUCTION,
                "\n\n",
            ]
            final_prompt_parts_fallback.extend(contents)

            # Get current config args and remove cached_content
            fallback_config_args = {
                "max_output_tokens": settings.LLM_MAX_TOKENS,
                "temperature": settings.LLM_TEMPERATURE,
                "safety_settings": config.safety_settings,
            }
            fallback_config = types.GenerateContentConfig(**fallback_config_args)

            try:
                # ATTEMPT 2: Fallback without cache
                logger.info(
                    "Calling Gemini generate_content for the second time (fallback without cache)."
                )
                response = await generate_with_retry(
                    client, model, final_prompt_parts_fallback, fallback_config
                )
                logger.info("Fallback generation without cache succeeded.")
                return response
            except Exception as fallback_error:
                logger.error(
                    f"The fallback generation attempt also failed: {fallback_error}",
                    exc_info=True,
                )
                raise Exception(
                    f"Error: LLM call failed with cache, and the fallback attempt also failed. Details: {fallback_error}"
                )
        else:
            # The error was a ClientError but not the one we handle for fallback
            logger.error(
                f"A non-cache-related ClientError occurred. This is not handled as a fallback. Error: {e}"
            )
            raise e

    except (RetryError, asyncio.TimeoutError) as e:
        logger.error(
            f"Initial LLM call failed after all retries or timed out: {e}",
            exc_info=True,
        )
        raise Exception(
            f"Error: The LLM API call failed after {settings.LLM_API_RETRY_ATTEMPTS} retries or timed out."
        )
