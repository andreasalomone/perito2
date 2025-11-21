"""File upload service for managing Gemini File Service uploads and deletions."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
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


async def upload_vision_file(
    client: genai.Client, file_path: str, display_name: str, mime_type: str
) -> Optional[types.File]:
    """Uploads a single file for vision processing to Gemini.

    Args:
        client: The Gemini API client.
        file_path: Path to the file to upload.
        display_name: Display name for the uploaded file.
        mime_type: MIME type of the file.

    Returns:
        Optional[types.File]: The uploaded File object, or None on error.
    """
    try:
        logger.debug(
            f"Attempting to upload file {display_name} from path: {file_path} to Gemini."
        )

        upload_config = types.UploadFileConfig(
            display_name=display_name,
            mime_type=mime_type,
        )

        @retry(
            stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
            wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
            retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
            reraise=True,
        )
        def _upload_file_with_retry():
            return client.files.upload(file=file_path, config=upload_config)

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


async def upload_vision_files(
    client: genai.Client, processed_files: List[Dict[str, Any]]
) -> Tuple[List[types.File], List[str], List[str]]:
    """Uploads all vision files from the processed files list.

    Args:
        client: The Gemini API client.
        processed_files: List of processed file information dictionaries.

    Returns:
        Tuple containing:
            - List of successfully uploaded File objects
            - List of file names for API reference
            - List of error messages for failed uploads
    """
    upload_coroutines = []
    file_display_names = []

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

            upload_coroutines.append(
                upload_vision_file(client, file_path, display_name, mime_type_from_info)
            )
            file_display_names.append(display_name)

    uploaded_file_objects: List[types.File] = []
    temp_uploaded_file_names_for_api: List[str] = []
    error_messages: List[str] = []

    if upload_coroutines:
        logger.info(
            f"Starting upload of {len(upload_coroutines)} vision files to Gemini."
        )
        upload_results = await asyncio.gather(
            *upload_coroutines, return_exceptions=False
        )
        successful_uploads = 0
        failed_uploads = 0

        for idx, result in enumerate(upload_results):
            display_name = file_display_names[idx]
            if isinstance(result, types.File):
                uploaded_file_objects.append(result)
                temp_uploaded_file_names_for_api.append(result.name)
                successful_uploads += 1
            else:
                error_messages.append(
                    f"\n\n[AVVISO: Il file {display_name} non ha potuto essere caricato per l'analisi.]\n\n"
                )
                failed_uploads += 1

        logger.info(
            f"Finished uploading vision files to Gemini. {successful_uploads} succeeded, {failed_uploads} failed."
        )

    return uploaded_file_objects, temp_uploaded_file_names_for_api, error_messages


async def delete_uploaded_file(client: genai.Client, file_name: str) -> bool:
    """Deletes a single uploaded file from Gemini File Service.

    Args:
        client: The Gemini API client.
        file_name: Name of the file to delete.

    Returns:
        bool: True if deletion succeeded, False otherwise.
    """
    try:
        logger.debug(
            f"Attempting to delete uploaded file {file_name} from Gemini File Service."
        )

        @retry(
            stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
            wait=wait_fixed(settings.LLM_API_RETRY_WAIT_SECONDS),
            retry=retry_if_exception_type(RETRIABLE_GEMINI_EXCEPTIONS),
            reraise=True,
        )
        def _delete_file_with_retry():
            client.files.delete(name=file_name)

        await asyncio.to_thread(_delete_file_with_retry)
        logger.debug(f"Successfully deleted file {file_name} from Gemini File Service.")
        return True
    except google_exceptions.NotFound:
        logger.warning(
            f"File {file_name} not found for deletion, or already deleted.",
            exc_info=False,
        )
        return False
    except RetryError as re:
        logger.error(
            f"Failed to delete file {file_name} from Gemini after multiple retries: {re}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Failed to delete file {file_name} from Gemini: {e}",
            exc_info=True,
        )
        return False


async def cleanup_uploaded_files(
    client: genai.Client, file_names: List[str]
) -> Tuple[int, int]:
    """Deletes multiple uploaded files from Gemini File Service.

    Args:
        client: The Gemini API client.
        file_names: List of file names to delete.

    Returns:
        Tuple containing (successful_deletions, failed_deletions).
    """
    if not file_names:
        return 0, 0

    logger.info(
        f"Cleaning up {len(file_names)} uploaded files from Gemini File Service."
    )

    delete_tasks = [delete_uploaded_file(client, name) for name in file_names]

    logger.info(
        f"Starting deletion of {len(delete_tasks)} files from Gemini File Service."
    )
    delete_results = await asyncio.gather(*delete_tasks)

    successful_deletions = sum(1 for success in delete_results if success)
    failed_deletions = len(delete_results) - successful_deletions

    logger.info(
        f"Finished deleting files from Gemini. {successful_deletions} deleted, {failed_deletions} failed or not found."
    )

    return successful_deletions, failed_deletions
