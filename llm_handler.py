"""LLM handler for generating insurance reports using Google Gemini."""
import asyncio
import logging
from typing import Any, Dict, List

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
) -> str:
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
        return "Error: LLM service is not configured (API key missing)."

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

        # Step 3: Build complete prompt parts
        prompt_parts = prompt_builder_service.build_prompt_parts(
            processed_files=processed_files,
            additional_text=additional_text,
            uploaded_file_objects=uploaded_file_objects,
            upload_error_messages=upload_error_messages,
            use_cache=bool(cache_name),
        )

        # Step 4: Build generation configuration
        config = generation_service.build_generation_config(cache_name)

        # Step 5: Generate report with retry and fallback logic
        logger.debug(
            "Sending request to Gemini. Model: %s. Using cache: %s",
            settings.LLM_MODEL_NAME,
            bool(cache_name),
        )

        response = await generation_service.generate_with_fallback(
            client=client,
            model=settings.LLM_MODEL_NAME,
            contents=prompt_parts,
            config=config,
        )

        # Step 6: Parse and validate response
        report_content = response_parser_service.parse_llm_response(response)
        # This already returns either the report or an "Error: ..." string.
        return report_content

    except asyncio.CancelledError:
        # Important for async correctness: don't swallow cancellations.
        logger.warning("Report generation task was cancelled.", exc_info=True)
        raise
    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini API error during report generation: %s", e, exc_info=True)
        return f"Error generating report due to an LLM API issue: {str(e)}"
    except Exception as e:  # noqa: BLE001 (we want a last-resort guardrail here)
        logger.error(
            "An unexpected error occurred with the Gemini service: %s",
            e,
            exc_info=True,
        )
        return f"Error generating report due to an unexpected LLM issue: {str(e)}"
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
    return asyncio.run(
        generate_report_from_content(processed_files, additional_text)
    )
