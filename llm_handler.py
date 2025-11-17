import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx  # For timeout in native async call
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import (
    AsyncRetrying,
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
    google_exceptions.DeadlineExceeded,  # Often means timeout, can be retried
    google_exceptions.InternalServerError,  # 500 errors from Google
    google_exceptions.Aborted,
    httpx.ReadTimeout,  # For async calls
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
)


async def _get_or_create_prompt_cache(client: genai.Client) -> Optional[str]:
    """Retries an existing prompt cache or creates a new one.

    Checks for a cache name in settings. If found, tries to retrieve it.
    If not found or invalid, creates a new cache with predefined prompts.

    Returns:
        Optional[str]: The name of the active cache, or None if an error occurs.
    """
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

            cache = await asyncio.to_thread(_get_cache_with_retry)
            # Enhanced cache validation
            logger.info(
                f"Retrieved cache: {cache.name}, model: {cache.model}, expires_time: {getattr(cache, 'expire_time', 'unknown')}"
            )
            # Basic validation: check if it's for the same model and not expired (implicitly, get succeeds)
            if cache.model.endswith(
                settings.LLM_MODEL_NAME
            ):  # Model name in cache includes 'models/' prefix
                logger.info(
                    f"Successfully retrieved and validated existing cache: {cache.name}"
                )
                active_cache_name = cache.name
            else:
                logger.warning(
                    f"Existing cache {existing_cache_name} is for a different model ({cache.model}) than expected ({settings.LLM_MODEL_NAME}). \
                    Will create a new cache for {settings.LLM_MODEL_NAME}."
                )
        except google_exceptions.NotFound:
            logger.warning(
                f"Existing cache {existing_cache_name} not found. Will create a new one."
            )
        except RetryError as re:  # Catch tenacity's RetryError after attempts exhausted
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
            # The role for prompt-like content for the system/model to use is typically 'user'
            # or 'model' if it's meant to be a pre-fill of a model's response.
            # Given these are instructions and reference texts, 'user' seems appropriate.
            cached_content_parts = [
                types.Content(
                    parts=[types.Part(text=GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI)],
                    role="user",
                ),
                types.Content(parts=[types.Part(text=SCHEMA_REPORT)], role="user"),
            ]

            ttl_seconds = settings.CACHE_TTL_DAYS * 24 * 60 * 60
            ttl_string = f"{ttl_seconds}s"

            # Ensure model name for cache creation is just the model ID, not prefixed with 'models/'
            # The client.caches.create expects the pure model ID like 'gemini-2.5-flash-preview-05-20-001'
            # while cache.model from a get() call returns 'models/gemini-2.5-flash-preview-05-20-001'.
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
                    model=model_id_for_creation,  # Use the raw model ID here
                    config={
                        "contents": cached_content_parts,  # Use the Content objects with roles
                        "system_instruction": types.Content(
                            parts=[types.Part(text=SYSTEM_INSTRUCTION)], role="system"
                        ),  # System instruction should have role "system"
                        "ttl": ttl_string,
                        "display_name": settings.CACHE_DISPLAY_NAME,
                    },
                )

            new_cache = await asyncio.to_thread(_create_cache_with_retry)
            active_cache_name = new_cache.name
            logger.info(
                f"Successfully created new cache: {active_cache_name} with TTL: {ttl_string}"
            )

            # Prepare the cache name for logging, ensuring no "cachedContents/" prefix.
            log_cache_name = active_cache_name.replace("cachedContents/", "")
            logger.info(
                f'To reuse this cache in future runs, set the environment variable REPORT_PROMPT_CACHE_NAME="{log_cache_name}"'
            )
        except RetryError as re:
            logger.error(
                f"Failed to create new prompt cache after multiple retries: {re}",
                exc_info=True,
            )
            return None  # Or return LLMGenerationResult with error
        except Exception as e:
            logger.error(f"Failed to create new prompt cache: {e}", exc_info=True)
            return None

    return active_cache_name


async def generate_report_from_content(
    processed_files: List[Dict[str, Any]], additional_text: str = ""
) -> str:
    """Generates an insurance report using Google Gemini with multimodal content and context caching."""
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured in settings.")
        return "Error: LLM service is not configured (API key missing)."

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    uploaded_file_objects: List[types.File] = []
    temp_uploaded_file_names_for_api: List[str] = []
    final_prompt_parts: List[Union[str, types.Part, types.File]] = []
    active_cache_name_for_generation: Optional[str] = None

    try:
        active_cache_name_for_generation = await _get_or_create_prompt_cache(client)

        if not active_cache_name_for_generation:
            logger.warning(
                "Proceeding with report generation without prompt caching due to an issue."
            )
            # Fallback: Include prompts directly if caching failed
            final_prompt_parts.extend(
                [
                    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI,
                    "\n\n",
                    SCHEMA_REPORT,
                    "\n\n",
                    SYSTEM_INSTRUCTION,  # Add system instruction if not using cache where it's embedded
                    "\n\n",
                ]
            )

        upload_coroutines = []
        processed_text_files_parts = []

        for file_info in processed_files:
            if file_info.get("type") == "vision":
                file_path = file_info.get("path")
                mime_type_from_info = file_info.get("mime_type")
                display_name = file_info.get(
                    "filename",
                    os.path.basename(file_path) if file_path else "uploaded_file",
                )
                if not file_path or not mime_type_from_info:
                    logger.warning(
                        f"Skipping vision file due to missing path or mime_type: {file_info}"
                    )
                    continue

                async def _upload_one_vision_file(
                    fp: str, display_name: str, mime_type: str
                ) -> Union[types.File, None]:
                    """Uploads a single file for vision processing to Gemini, handling potential errors."""
                    try:
                        logger.debug(
                            f"Attempting to upload file {display_name} from path: {fp} to Gemini."
                        )
                        # Corrected keyword from 'path' to 'file' based on recent SDK versions
                        upload_config = types.UploadFileConfig(
                            display_name=display_name,
                            mime_type=mime_type,
                            # You might need to set other fields like mime_type if not automatically detected
                            # mime_type="image/jpeg" # or "application/pdf", etc.
                        )

                        @retry(
                            stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
                            wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
                            retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
                            reraise=True,
                        )
                        def _upload_file_with_retry():
                            # Note: The client.files.upload might have its own timeout.
                            # We are adding retries around it.
                            return client.files.upload(file=fp, config=upload_config)

                        uploaded_file = await asyncio.to_thread(_upload_file_with_retry)
                        logger.debug(
                            f"Successfully uploaded file {display_name} (URI: {uploaded_file.uri}) to Gemini."
                        )
                        return uploaded_file
                    except RetryError as re:
                        logger.error(
                            f"Failed to upload file {display_name} to Gemini after multiple retries: {re}",
                            exc_info=True,
                        )
                        return None
                    except Exception as e:
                        logger.error(
                            f"Failed to upload file {display_name} to Gemini: {e}",
                            exc_info=True,
                        )
                        return None

                upload_coroutines.append(
                    _upload_one_vision_file(
                        file_path, display_name, mime_type_from_info
                    )
                )

            elif file_info.get("type") == "text":
                filename = file_info.get("filename", "documento testuale")
                content = file_info.get("content", "")
                if content:
                    processed_text_files_parts.append(
                        f"--- INIZIO CONTENUTO DA FILE: {filename} ---\n"
                    )
                    processed_text_files_parts.append(content)
                    processed_text_files_parts.append(
                        f"\n--- FINE CONTENUTO DA FILE: {filename} ---\n\n"
                    )
            elif file_info.get("type") == "error":
                filename = file_info.get("filename", "file sconosciuto")
                message = file_info.get("message", "errore generico")
                processed_text_files_parts.append(
                    f"\n\n[AVVISO: Problema durante l'elaborazione del file {filename}: {message}]\n\n"
                )
            elif file_info.get("type") == "unsupported":
                filename = file_info.get("filename", "file sconosciuto")
                message = file_info.get("message", "tipo non supportato")
                processed_text_files_parts.append(
                    f"\n\n[AVVISO: Il file {filename} è di un tipo non supportato e non può essere processato: {message}]\n\n"
                )

        if upload_coroutines:
            logger.info(
                f"Starting upload of {len(upload_coroutines)} vision files to Gemini."
            )
            upload_results = await asyncio.gather(
                *upload_coroutines, return_exceptions=False
            )  # return_exceptions=False handled in _upload_one_vision_file
            successful_uploads = 0
            failed_uploads = 0
            for result in upload_results:
                if isinstance(result, types.File):
                    uploaded_file_objects.append(result)
                    temp_uploaded_file_names_for_api.append(result.name)
                    successful_uploads += 1
                elif (
                    isinstance(result, tuple)
                    and len(result) == 2
                    and isinstance(result[1], Exception)
                ):
                    display_name, _ = (
                        result  # Exception already logged in _upload_one_vision_file
                    )
                    final_prompt_parts.append(
                        f"\n\n[AVVISO: Il file {display_name} non ha potuto essere caricato per l'analisi.]\n\n"
                    )
                    failed_uploads += 1
                else:  # Should ideally not happen if _upload_one_vision_file returns File or None (which implies error logged)
                    logger.warning(
                        f"Unexpected result type from _upload_one_vision_file: {type(result)}. Counting as failed upload."
                    )
                    failed_uploads += 1
            logger.info(
                f"Finished uploading vision files to Gemini. {successful_uploads} succeeded, {failed_uploads} failed."
            )

        final_prompt_parts.extend(
            processed_text_files_parts
        )  # Add text file parts after vision processing

        if additional_text.strip():
            final_prompt_parts.append(
                f"--- INIZIO TESTO AGGIUNTIVO FORNITO ---\n{additional_text}\n--- FINE TESTO AGGIUNTIVO FORNITO ---\n"
            )

        # Add uploaded file objects (references) to the prompt parts
        # These are `types.File` objects, which the API handles as references to uploaded content.
        final_prompt_parts.extend(uploaded_file_objects)

        final_instruction = "\n\nAnalizza TUTTI i documenti, foto e testi forniti (sia quelli caricati come file referenziati, sia quelli inclusi direttamente come testo) e genera il report."
        if active_cache_name_for_generation:
            final_instruction += " Utilizza le istruzioni di stile, struttura e sistema precedentemente cachate."
        else:
            final_instruction += " Utilizza le istruzioni di stile, struttura e sistema fornite all'inizio di questo prompt."
        final_prompt_parts.append(final_instruction)

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

        if active_cache_name_for_generation:
            generation_config_args["cached_content"] = active_cache_name_for_generation
            logger.info(
                f"Using cached content: {active_cache_name_for_generation} for report generation."
            )

        final_config = types.GenerateContentConfig(**generation_config_args)

        logger.debug(
            f"Sending request to Gemini. Model: {settings.LLM_MODEL_NAME}. Using cache: {bool(active_cache_name_for_generation)}. Config: {final_config}"
        )
        # Add logging for cache details
        if active_cache_name_for_generation:
            logger.info(
                f"Request will use cached content: {active_cache_name_for_generation}"
            )
        else:
            logger.info(
                "Request will NOT use cached content (prompts included directly)"
            )

        # Use client.aio.models.generate_content for async call
        response = None

        # --- Main Generation Logic ---
        # We first try with the cache. If that fails with a specific, non-retriable
        # ClientError related to the cache, we then attempt a fallback without it.

        try:
            # ATTEMPT 1: With cache (if available)
            logger.info(
                "Attempting LLM generation with current settings (including cache if configured)."
            )
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
                            model=settings.LLM_MODEL_NAME,
                            contents=final_prompt_parts,
                            config=final_config,
                        ),
                        timeout=settings.LLM_API_TIMEOUT_SECONDS,
                    )

        except genai_errors.ClientError as e:
            # This block catches non-retriable client errors from the first attempt.
            # The most important one to handle is a potential cache-related error.
            logger.warning(
                f"Initial LLM call failed with a non-retriable ClientError: {e}"
            )

            is_cache_error = (
                active_cache_name_for_generation
                and "INVALID_ARGUMENT" in str(e)
                and (
                    "400" in str(e)
                    or (hasattr(e, "status_code") and e.status_code == 400)
                )
            )

            if is_cache_error:
                logger.warning(
                    "Cache-related INVALID_ARGUMENT error detected. Attempting fallback generation without cache."
                )

                # Rebuild config without cache and include prompts directly
                # This is necessary because the original prompt parts might not have the full text
                # if caching was expected to work.
                final_prompt_parts_fallback = [
                    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI,
                    "\n\n",
                    SCHEMA_REPORT,
                    "\n\n",
                    SYSTEM_INSTRUCTION,
                    "\n\n",
                ]
                final_prompt_parts_fallback.extend(
                    final_prompt_parts
                )  # Add the content parts

                fallback_config_args = {
                    k: v
                    for k, v in generation_config_args.items()
                    if k != "cached_content"
                }
                fallback_config = types.GenerateContentConfig(**fallback_config_args)

                try:
                    # ATTEMPT 2: Fallback without cache
                    logger.info(
                        "Calling Gemini generate_content for the second time (fallback without cache)."
                    )
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
                        wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
                        retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
                        reraise=True,
                    ):
                        with attempt:
                            response = await asyncio.wait_for(
                                client.aio.models.generate_content(
                                    model=settings.LLM_MODEL_NAME,
                                    contents=final_prompt_parts_fallback,
                                    config=fallback_config,
                                ),
                                timeout=settings.LLM_API_TIMEOUT_SECONDS,
                            )
                    logger.info("Fallback generation without cache succeeded.")
                except Exception as fallback_error:
                    logger.error(
                        f"The fallback generation attempt also failed: {fallback_error}",
                        exc_info=True,
                    )
                    # Return a clear error indicating both attempts failed.
                    return f"Error: LLM call failed with cache, and the fallback attempt also failed. Details: {fallback_error}"
            else:
                # The error was a ClientError but not the one we handle for fallback. Re-raise it.
                logger.error(
                    f"A non-cache-related ClientError occurred. This is not handled as a fallback. Error: {e}"
                )
                raise e

        except (RetryError, asyncio.TimeoutError) as e:
            # This block catches errors from the first attempt if all retries failed.
            logger.error(
                f"Initial LLM call failed after all retries or timed out: {e}",
                exc_info=True,
            )
            return f"Error: The LLM API call failed after {settings.LLM_API_RETRY_ATTEMPTS} retries or timed out."

        if response is None:
            # This is a safeguard. If we've gotten here, response should have a value
            # or an exception should have been raised.
            logger.error(
                "LLM response is unexpectedly None after all generation attempts and fallbacks."
            )
            return "Error: LLM response was unexpectedly None after all processing."

        report_content: str = ""

        try:
            if response.text:
                report_content = response.text
            elif response.candidates:
                parts_text: List[str] = []
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "text") and part.text is not None:
                                parts_text.append(part.text)
                if parts_text:
                    report_content = "".join(parts_text)
        except AttributeError as e:
            logger.warning(
                f"AttributeError while accessing response text or parts: {e}.",
                exc_info=True,
            )
            # Log the full response separately if needed for debugging, but don't include in common path
            # logger.debug(f"Full response object on AttributeError: {response}")

        if not report_content:
            logger.warning(f"Gemini response did not yield usable text content.")
            # Log the full response separately if needed for debugging
            # logger.debug(f"Full response object when no usable text: {response}")
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_obj = response.prompt_feedback.block_reason
                block_reason_name = (
                    block_reason_obj.name
                    if hasattr(block_reason_obj, "name")
                    else str(block_reason_obj)
                )
                logger.error(
                    f"Content generation blocked. Reason from prompt_feedback: {block_reason_name}"
                )
                return f"Error: Content generation blocked by the LLM. Reason: {block_reason_name}"
            if response.candidates:
                first_candidate = response.candidates[0]
                if first_candidate.finish_reason:
                    finish_reason_obj = first_candidate.finish_reason
                    finish_reason_name = (
                        finish_reason_obj.name
                        if hasattr(finish_reason_obj, "name")
                        else str(finish_reason_obj)
                    )
                    if finish_reason_name == types.FinishReason.MAX_TOKENS.name:
                        logger.warning("Content generation stopped due to MAX_TOKENS.")
                        return "Error: Content generation reached maximum token limit. The generated text may be incomplete."
                    elif finish_reason_name != types.FinishReason.STOP.name:
                        logger.error(
                            f"Content generation stopped for reason: {finish_reason_name}."
                        )
                        return f"Error: LLM generation stopped for reason: {finish_reason_name}."
                    elif (
                        finish_reason_name == types.FinishReason.STOP.name
                        and not report_content
                    ):
                        logger.warning(
                            "LLM generation finished (STOP), but no text content was extracted."
                        )
                        return "Error: LLM generation completed, but no usable text was found in the response."
            else:
                logger.error(
                    "No candidates found in LLM response and not blocked by prompt_feedback."
                )
            if not report_content:
                logger.error(
                    f"Unknown issue: No text in Gemini response. Prompt Feedback: {response.prompt_feedback}. Candidate 0 Finish Reason (if any): {response.candidates[0].finish_reason if response.candidates else 'N/A'}"
                )
                return (
                    "Error: Unknown issue with LLM response, no text content received."
                )

        logger.info("Report content successfully generated.")
        return report_content

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini API Error: {e}", exc_info=True)
        return f"Error generating report due to an LLM API issue: {str(e)}"
    except Exception as e:
        logger.error(
            f"An unexpected error occurred with the Gemini service: {e}", exc_info=True
        )
        return f"Error generating report due to an unexpected LLM issue: {str(e)}"
    finally:
        if temp_uploaded_file_names_for_api:
            logger.info(
                f"Cleaning up {len(temp_uploaded_file_names_for_api)} uploaded files from Gemini File Service."
            )
            delete_tasks = []

            async def _delete_one_file(name_to_delete: str):
                try:
                    logger.debug(
                        f"Attempting to delete uploaded file {name_to_delete} from Gemini File Service."
                    )

                    @retry(
                        stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
                        wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
                        retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
                        reraise=True,
                    )
                    def _delete_file_with_retry():
                        client.files.delete(name=name_to_delete)

                    await asyncio.to_thread(_delete_file_with_retry)
                    logger.debug(
                        f"Successfully deleted file {name_to_delete} from Gemini File Service."
                    )
                    return True, name_to_delete
                except google_exceptions.NotFound:
                    logger.warning(
                        f"File {name_to_delete} not found for deletion, or already deleted.",
                        exc_info=False,
                    )
                    return (
                        False,
                        name_to_delete,
                    )  # Indicate failure but not critical error
                except RetryError as re:
                    logger.error(
                        f"Failed to delete file {name_to_delete} from Gemini after multiple retries: {re}",
                        exc_info=True,
                    )
                    return False, name_to_delete
                except Exception as e:
                    logger.error(
                        f"Failed to delete file {name_to_delete} from Gemini: {e}",
                        exc_info=True,
                    )
                    return False, name_to_delete  # Indicate failure

            for name_to_delete in temp_uploaded_file_names_for_api:
                delete_tasks.append(_delete_one_file(name_to_delete))

            if delete_tasks:
                logger.info(
                    f"Starting deletion of {len(delete_tasks)} files from Gemini File Service."
                )
                delete_results = await asyncio.gather(*delete_tasks)
                successful_deletions = sum(
                    1 for success, _ in delete_results if success
                )
                failed_deletions = len(delete_results) - successful_deletions
                logger.info(
                    f"Finished deleting files from Gemini. {successful_deletions} deleted, {failed_deletions} failed or not found."
                )

    return (
        "Error: An unexpected issue occurred before report content could be determined."
    )


# Example of how you might want to initialize or check the cache at startup
# (e.g., in your app.py or a main script)
# async def ensure_prompt_cache_exists(): # Would need to be async
#     if not settings.GEMINI_API_KEY:
#         logger.warning("Cannot ensure prompt cache: GEMINI_API_KEY not set.")
#         return
#     try:
#        client = genai.Client(api_key=settings.GEMINI_API_KEY)
#        cache_name = await _get_or_create_prompt_cache(client) # await async call
#        if cache_name:
#            logger.info(f"Prompt cache is active: {cache_name}")
#            # Optionally, you could try to update settings.REPORT_PROMPT_CACHE_NAME here
#            # if it was newly created and not set in .env, though that\'s harder to persist back to .env
#        else:
#            logger.error("Failed to ensure prompt cache is active.")
#     except Exception as e:
#        logger.error(f"Error during prompt cache initialization: {e}", exc_info=True)

# if __name__ == '__main__':
#     # This is just for testing the cache creation/retrieval logic directly
#     # In a real app, this would be part of your application's startup sequence or first request.
#     async def main_test(): # Main test function would need to be async
#         logging.basicConfig(level=logging.INFO)
#         # Ensure you have GEMINI_API_KEY in your .env or environment
#         # And optionally REPORT_PROMPT_CACHE_NAME set to an existing cache ID
#         if not settings.GEMINI_API_KEY:
#             print("Please set GEMINI_API_KEY in your .env file to test caching.")
#         else:
#             print(f"GEMINI_API_KEY found. Model for caching: {settings.LLM_MODEL_NAME}")
#             print(f"Configured CACHE_TTL_DAYS: {settings.CACHE_TTL_DAYS}")
#             print(f"Configured CACHE_DISPLAY_NAME: {settings.CACHE_DISPLAY_NAME}")
#             print(f"Current REPORT_PROMPT_CACHE_NAME from env (if any): {settings.REPORT_PROMPT_CACHE_NAME}")

#             test_client = genai.Client(api_key=settings.GEMINI_API_KEY)
#             active_cache = await _get_or_create_prompt_cache(test_client) # await async call
#             if active_cache:
#                 print(f"Test successful. Active cache name: {active_cache}")
#                 print(f"Try setting REPORT_PROMPT_CACHE_NAME='{active_cache.replace('cachedContents/', '')}' in your .env file for the next run.")

#                 # Test retrieving it again to simulate next run with env var set
#                 # For this test to work, you'd manually set the env var for the next line if it was just created.
#                 # Or, if settings.REPORT_PROMPT_CACHE_NAME was already set and valid, this confirms retrieval.
#                 # settings.REPORT_PROMPT_CACHE_NAME = active_cache # Simulate it being set for the next call
#                 # print("\nAttempting to retrieve the cache again...")
#                 # retrieved_again = await _get_or_create_prompt_cache(test_client) # await async call
#                 # if retrieved_again == active_cache:
#                 #     print(f"Second retrieval successful: {retrieved_again}")
#                 # else:
#                 #     print(f"Second retrieval failed or got a different cache: {retrieved_again}")
#             else:
#                 print("Test failed to get or create cache.")
#     asyncio.run(main_test()) # Run the async main test function
