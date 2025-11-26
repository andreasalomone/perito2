"""LLM handler for generating insurance reports using Google Gemini."""

import asyncio
import logging
from typing import Any, Dict, List, Tuple

from google import genai
from google.api_core import exceptions as google_exceptions

from core.config import settings
from services.llm import (
    cache_service,
    file_upload_service,
    generation_service,
    prompt_builder_service,
    response_parser_service,
)

logger = logging.getLogger(__name__)


async def generate_report_from_content(
    processed_files: List[Dict[str, Any]], additional_text: str = ""
) -> Tuple[str, float, Dict[str, int]]:
    """Generate an insurance report using Google Gemini with multimodal content and context caching.

    Orchestrates the report generation by:
      1. Initializing the Gemini client
      2. Managing prompt cache
      3. Uploading vision files (PDFs, images) to Gemini
      4. Building the complete prompt with all content
      5. Calling the LLM with retry and fallback logic
      6. Parsing and validating the response
      7. Cleaning up uploaded files

    Args:
        processed_files: List of processed file information dictionaries containing
            file type, path, content, and metadata.
        additional_text: Optional additional text to include in the prompt.

    Returns:
        The generated report content as a string, or an error message starting with "Error:".
        The API cost in USD.
        A dictionary containing token usage details.
    """
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured in settings.")
        return "Error: LLM service is not configured (API key missing).", 0.0, {}

    client: genai.Client = genai.Client(api_key=settings.GEMINI_API_KEY)
    uploaded_file_names: List[str] = []

    try:
        # Step 1: Get or create prompt cache (run in a thread to avoid blocking)
        cache_name = await asyncio.to_thread(
            cache_service.get_or_create_prompt_cache, client
        )

        if cache_name:
            logger.info("Using existing prompt cache: %s", cache_name)
        else:
            logger.warning(
                "Proceeding with report generation without prompt caching due to an issue."
            )

        logger.info(
            "Generating report from %d processed files. Using cache: %s",
            len(processed_files),
            bool(cache_name),
        )

        # Step 2: Upload vision files to Gemini
        (
            uploaded_file_objects,
            uploaded_file_names,
            upload_error_messages,
        ) = await file_upload_service.upload_vision_files(client, processed_files)

        # Helper to build prompt (with or without cache)
        def _get_prompt_parts(use_cache_flag: bool) -> List[Any]:
            return prompt_builder_service.build_prompt_parts(
                processed_files=processed_files,
                additional_text=additional_text,
                uploaded_file_objects=uploaded_file_objects,
                upload_error_messages=upload_error_messages,
                use_cache=use_cache_flag,
            )

        # --- Linear Retry Logic ---

        response = None
        last_exception = None

        # ATTEMPT 1: Primary Model (with cache if available)
        current_model = settings.LLM_MODEL_NAME
        use_cache = bool(cache_name)

        try:
            logger.debug(
                f"Attempt 1: Sending request to Gemini. Model: {current_model}. Using cache: {use_cache}"
            )
            prompt_parts = _get_prompt_parts(use_cache)
            config = generation_service.build_generation_config(
                cache_name if use_cache else None
            )

            response = await generation_service.generate_with_retry(
                client=client,
                model=current_model,
                contents=prompt_parts,
                config=config,
            )
        except genai.errors.ClientError as e:
            # Check for Cache Invalid/Expired (400 INVALID_ARGUMENT)
            if (
                use_cache
                and "INVALID_ARGUMENT" in str(e)
                and ("400" in str(e) or getattr(e, "status_code", 0) == 400)
            ):
                logger.warning(
                    "Attempt 1 failed: Cache invalid/expired. Proceeding to Attempt 2 (No Cache)."
                )
                last_exception = e
            else:
                raise  # Re-raise other ClientErrors immediately
        except genai.errors.ServerError as e:
            # Check for Overload (503 UNAVAILABLE)
            if "503" in str(e) or "overloaded" in str(e).lower():
                logger.warning(
                    "Attempt 1 failed: Server overloaded. Proceeding to Attempt 3 (Fallback)."
                )
                last_exception = e
                # Proceed to Attempt 2 (No Cache) as per linear flow, though overload might persist.
                pass
            else:
                raise  # Re-raise other ServerErrors

        # ATTEMPT 2: Primary Model WITHOUT Cache (if Attempt 1 failed and response is None)
        # Skip this attempt if the previous failure was an Overload error (Attempt 1),
        # as retrying the same model immediately is unlikely to help.
        is_overload_failure = isinstance(last_exception, genai.errors.ServerError) and (
            "503" in str(last_exception) or "overloaded" in str(last_exception).lower()
        )

        if response is None and not is_overload_failure:
            use_cache = False
            try:
                logger.debug(f"Attempt 2: Retrying with {current_model} without cache.")
                prompt_parts = _get_prompt_parts(use_cache)
                config = generation_service.build_generation_config(None)

                response = await generation_service.generate_with_retry(
                    client=client,
                    model=current_model,
                    contents=prompt_parts,
                    config=config,
                )
            except genai.errors.ServerError as e:
                if "503" in str(e) or "overloaded" in str(e).lower():
                    logger.warning(
                        f"Attempt 2 failed: Model {current_model} overloaded. Proceeding to Attempt 3 (Fallback)."
                    )
                    last_exception = e
                else:
                    raise  # Re-raise other ServerErrors
            except Exception as e:
                # If it was a ClientError from Attempt 1 that we caught, we might catch another one here?
                # Attempt 2 shouldn't have cache errors.
                logger.warning(f"Attempt 2 failed with unexpected error: {e}")
                last_exception = e
                # Fall through to Attempt 3

        # ATTEMPT 3: Fallback Model (if Attempt 2 failed and response is None)
        if response is None and settings.LLM_FALLBACK_MODEL_NAME:
            fallback_model = settings.LLM_FALLBACK_MODEL_NAME
            logger.warning(f"Attempt 3: Switching to fallback model: {fallback_model}")

            try:
                # Ensure No Cache for fallback
                prompt_parts = _get_prompt_parts(False)
                config = generation_service.build_generation_config(None)

                response = await generation_service.generate_with_retry(
                    client=client,
                    model=fallback_model,
                    contents=prompt_parts,
                    config=config,
                )
                logger.info(f"Fallback to {fallback_model} succeeded.")
            except Exception as e:
                logger.error(f"Attempt 3 (Fallback) failed: {e}")
                raise e  # If fallback fails, we give up.

        if response is None:
            if last_exception:
                raise last_exception
            else:
                raise Exception("LLM generation failed (unknown state).")

        # Step 6: Parse and validate response
        report_content = response_parser_service.parse_llm_response(response)

        # Calculate cost
        usage_metadata = getattr(response, "usage_metadata", None)
        api_cost_usd = generation_service.calculate_cost(usage_metadata)

        # Extract token counts
        token_usage = {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "total_token_count": 0,
            "cached_content_token_count": 0,
        }
        if usage_metadata:
            token_usage["prompt_token_count"] = getattr(
                usage_metadata, "prompt_token_count", 0
            )
            token_usage["candidates_token_count"] = getattr(
                usage_metadata, "candidates_token_count", 0
            )
            token_usage["total_token_count"] = getattr(
                usage_metadata, "total_token_count", 0
            )
            token_usage["cached_content_token_count"] = getattr(
                usage_metadata, "cached_content_token_count", 0
            )

        return report_content, api_cost_usd, token_usage

    except asyncio.CancelledError:
        # Important for async correctness: don't swallow cancellations.
        logger.warning("Report generation task was cancelled.", exc_info=True)
        raise
    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini API error during report generation: %s", e, exc_info=True)
        return f"Error generating report due to an LLM API issue: {str(e)}", 0.0, {}
    except Exception as e:  # noqa: BLE001 (we want a last-resort guardrail here)
        logger.error(
            "An unexpected error occurred with the Gemini service: %s",
            e,
            exc_info=True,
        )
        return (
            f"Error generating report due to an unexpected LLM issue: {str(e)}",
            0.0,
            {},
        )
    finally:
        # Step 7: Cleanup uploaded files (best-effort, don't override main errors)
        if uploaded_file_names:
            try:
                await file_upload_service.cleanup_uploaded_files(
                    client, uploaded_file_names
                )
            except Exception as cleanup_error:  # noqa: BLE001
                logger.warning(
                    "Failed to clean up uploaded files: %s",
                    cleanup_error,
                    exc_info=True,
                )


def generate_report_from_content_sync(
    processed_files: List[Dict[str, Any]], additional_text: str = ""
) -> Tuple[str, float, Dict[str, int]]:
    """Synchronous wrapper for generate_report_from_content."""
    return asyncio.run(generate_report_from_content(processed_files, additional_text))
