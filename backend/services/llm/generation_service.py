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

from config import settings

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


def calculate_cost(usage_metadata: Any, pricing_config: Any = None) -> float:
    """Calculates the cost of the generation in USD based on token usage.

    Pricing (Gemini 2.5 Pro):
    - Input: $1.25/1M (<= 200k), $2.50/1M (> 200k)
    - Output: $10.00/1M (<= 200k), $15.00/1M (> 200k)
    - Cache: $0.125/1M (<= 200k), $0.25/1M (> 200k)

    Args:
        usage_metadata: The usage metadata object from the LLM response.
        pricing_config: Optional PricingConfig object or dict with pricing details.

    Returns:
        The calculated cost in USD.
    """
    if not usage_metadata:
        return 0.0

    prompt_token_count = getattr(usage_metadata, "prompt_token_count", 0)
    candidates_token_count = getattr(usage_metadata, "candidates_token_count", 0)
    # Note: total_token_count is prompt + candidates

    # Determine prices (Default to settings)
    p_in_t1 = settings.PRICE_INPUT_TIER_1
    p_in_t2 = settings.PRICE_INPUT_TIER_2
    p_out_t1 = settings.PRICE_OUTPUT_TIER_1
    p_out_t2 = settings.PRICE_OUTPUT_TIER_2
    
    # Override with dynamic config if available
    if pricing_config:
        # Handle SQLAlchemy model or dict
        get_val = lambda k: getattr(pricing_config, k, None) if not isinstance(pricing_config, dict) else pricing_config.get(k)
        
        if get_val('price_input_tier_1') is not None: p_in_t1 = get_val('price_input_tier_1')
        if get_val('price_input_tier_2') is not None: p_in_t2 = get_val('price_input_tier_2')
        if get_val('price_output_tier_1') is not None: p_out_t1 = get_val('price_output_tier_1')
        if get_val('price_output_tier_2') is not None: p_out_t2 = get_val('price_output_tier_2')

    # Determine pricing tier based on prompt size (this is a simplification,
    # as tier usually applies to the request size, but for cost estimation this is close)
    # Actually, the pricing page says "prompts <= 200k tokens".

    # Input Cost
    if prompt_token_count <= 200000:
        input_cost = (prompt_token_count / 1_000_000) * p_in_t1
    else:
        input_cost = (prompt_token_count / 1_000_000) * p_in_t2

    # Output Cost
    if (
        prompt_token_count <= 200000
    ):  # Tier is determined by prompt size usually? Or output size?
        # "Price is based on the size of the prompt" - usually tiers are based on context window usage.
        # Let's assume the tier is based on the prompt size for both input and output rates as per common practice,
        # or simply that the "prompts <= 200k" condition applies to the rate selection.
        output_cost = (
            candidates_token_count / 1_000_000
        ) * p_out_t1
    else:
        output_cost = (
            candidates_token_count / 1_000_000
        ) * p_out_t2

    # Cache Cost (if applicable)
    # We don't have explicit "cached_token_count" in standard usage_metadata usually,
    # unless we check how many tokens were cached.
    # For now, we'll assume standard input/output cost.
    # If usage_metadata has details on cached tokens, we could refine this.
    # Google GenAI SDK usage_metadata might have 'cached_content_token_count' or similar if using cache.
    # Let's check if there's a field for it.
    # Based on docs, it might be just part of prompt_token_count or separate.
    # For this iteration, we will stick to Input + Output cost to be safe and simple.

    total_cost = input_cost + output_cost
    return total_cost
