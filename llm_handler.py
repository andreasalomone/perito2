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
) -> Tuple[str, float]:
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
    """
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured in settings.")
        return "Error: LLM service is not configured (API key missing).", 0.0

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

        # Initial attempt configuration
        current_model = settings.LLM_MODEL_NAME
        use_cache_current = bool(cache_name)
        
        # Build initial prompt and config
        prompt_parts = _get_prompt_parts(use_cache_current)
        config = generation_service.build_generation_config(cache_name if use_cache_current else None)

        try:
            # ATTEMPT 1: Primary Model (with cache if available)
            logger.debug(f"Attempt 1: Sending request to Gemini. Model: {current_model}. Using cache: {use_cache_current}")
            response = await generation_service.generate_with_retry(
                client=client,
                model=current_model,
                contents=prompt_parts,
                config=config,
            )

        except genai.errors.ClientError as e:
            # Handle Cache Invalid/Expired (400 INVALID_ARGUMENT)
            is_cache_error = (
                use_cache_current
                and "INVALID_ARGUMENT" in str(e)
                and ("400" in str(e) or (hasattr(e, "status_code") and e.status_code == 400))
            )

            if is_cache_error:
                logger.warning("Attempt 1 failed: Cache invalid/expired. Retrying without cache.")
                # ATTEMPT 2: Primary Model WITHOUT Cache
                use_cache_current = False
                prompt_parts = _get_prompt_parts(use_cache_current) # Rebuild prompt with full text
                config = generation_service.build_generation_config(None) # Config without cache
                
                try:
                    logger.debug(f"Attempt 2: Retrying with {current_model} without cache.")
                    response = await generation_service.generate_with_retry(
                        client=client,
                        model=current_model,
                        contents=prompt_parts,
                        config=config,
                    )
                except Exception as retry_error:
                    # If retry fails, check for overload to try fallback model
                    if "503" in str(retry_error) or "overloaded" in str(retry_error).lower():
                         logger.warning(f"Attempt 2 failed: Model {current_model} overloaded. Trying fallback model.")
                         # Proceed to fallback model logic below (shared)
                         raise retry_error 
                    else:
                        raise # Re-raise other errors
            else:
                raise # Re-raise non-cache ClientErrors

        except genai.errors.ServerError as e:
            # Handle Overloaded (503 UNAVAILABLE) - caught from Attempt 1
            logger.warning(f"Attempt 1 failed: Server error ({e}). Checking for overload...")
            raise # Re-raise to be caught by outer try/except or handled here? 
            # Actually, let's handle it here to keep flow linear or use a loop. 
            # But simpler: just let it raise and catch generic Exception? No, we want specific handling.
            # Let's restructure to use a loop or explicit steps.
            pass # Fall through to fallback logic if needed, but we need to know if it was overload.

        # Wait, the try/except block above is getting messy. Let's simplify.
        # We need to handle:
        # 1. Cache Error -> Retry No Cache
        # 2. Overload Error (from 1 or 2) -> Retry Fallback Model (No Cache)
        
    except (genai.errors.ClientError, genai.errors.ServerError) as e:
        # Unified Error Handling and Fallback Logic
        
        # Check if we should try fallback model
        should_try_fallback = False
        fallback_reason = ""
        
        # Check for Cache Error (400)
        is_cache_error = (
            bool(cache_name)
            and isinstance(e, genai.errors.ClientError)
            and "INVALID_ARGUMENT" in str(e)
        )
        
        # Check for Overload (503)
        is_overloaded = (
            isinstance(e, genai.errors.ServerError)
            and ("503" in str(e) or "overloaded" in str(e).lower())
        )

        if is_cache_error:
            logger.warning("LLM Cache invalid/expired. Switching to non-cached request.")
            # Prepare for retry without cache
            use_cache_current = False
            prompt_parts = _get_prompt_parts(use_cache_current)
            config = generation_service.build_generation_config(None)
            
            try:
                # Retry with Primary Model + No Cache
                logger.info(f"Retrying with {current_model} (No Cache)...")
                response = await generation_service.generate_with_retry(
                    client=client, model=current_model, contents=prompt_parts, config=config
                )
                # If successful, we are done
            except genai.errors.ServerError as e2:
                # If retry fails with overload, mark for fallback
                if "503" in str(e2) or "overloaded" in str(e2).lower():
                    is_overloaded = True
                    e = e2 # Update exception to the latest one
                else:
                    raise e2 # Re-raise other server errors
            except Exception as e2:
                raise e2 # Re-raise other errors

        # If we are here and is_overloaded is True (either from initial call or cache retry)
        if is_overloaded and settings.LLM_FALLBACK_MODEL_NAME:
            fallback_model = settings.LLM_FALLBACK_MODEL_NAME
            logger.warning(f"Model {current_model} overloaded. Switching to fallback: {fallback_model}")
            
            # Ensure we are using No Cache for fallback (different model = different cache)
            use_cache_current = False
            prompt_parts = _get_prompt_parts(use_cache_current)
            config = generation_service.build_generation_config(None)
            
            # Retry with Fallback Model
            response = await generation_service.generate_with_retry(
                client=client, model=fallback_model, contents=prompt_parts, config=config
            )
            logger.info(f"Fallback to {fallback_model} succeeded.")
        elif is_overloaded:
             logger.error("Model overloaded but no fallback model configured.")
             raise e
        elif not is_cache_error: # If it wasn't a cache error and we didn't handle it above
             raise e

        # If we reached here without raising, 'response' should be set from one of the retries.
        if not response:
            raise Exception("LLM generation failed (unknown state).")

        # Step 6: Parse and validate response
        report_content = response_parser_service.parse_llm_response(response)

        # Calculate cost
        usage_metadata = getattr(response, "usage_metadata", None)
        api_cost_usd = generation_service.calculate_cost(usage_metadata)

        return report_content, api_cost_usd

        # Success path for Attempt 1
        report_content = response_parser_service.parse_llm_response(response)
        usage_metadata = getattr(response, "usage_metadata", None)
        api_cost_usd = generation_service.calculate_cost(usage_metadata)
        return report_content, api_cost_usd

    except asyncio.CancelledError:
        # Important for async correctness: don't swallow cancellations.
        logger.warning("Report generation task was cancelled.", exc_info=True)
        raise
    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini API error during report generation: %s", e, exc_info=True)
        return f"Error generating report due to an LLM API issue: {str(e)}", 0.0
    except Exception as e:  # noqa: BLE001 (we want a last-resort guardrail here)
        logger.error(
            "An unexpected error occurred with the Gemini service: %s",
            e,
            exc_info=True,
        )
        return f"Error generating report due to an unexpected LLM issue: {str(e)}", 0.0
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
) -> str:
    """Synchronous wrapper for generate_report_from_content."""
    return asyncio.run(generate_report_from_content(processed_files, additional_text))
