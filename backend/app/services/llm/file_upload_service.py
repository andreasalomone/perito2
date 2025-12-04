"""
Gemini File Service Manager.

Handles secure upload, lifecycle management, and deletion of files within
the Vertex AI/Gemini ecosystem. Enforces strict concurrency limits and
robust error handling.
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Sequence

import httpx
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.gcs_service import download_file_to_temp

# Configure Module Logger
logger = logging.getLogger(__name__)

# Constants
MAX_CONCURRENT_UPLOADS = 5  # Prevent thread pool starvation
MAX_CONCURRENT_DELETES = 10

# Define Retriable Exceptions explicitly
RETRIABLE_EXCEPTIONS = (
    google_exceptions.ServiceUnavailable,
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
    google_exceptions.Aborted,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
)

# --- Type Definitions ---

@dataclass(frozen=True)
class UploadCandidate:
    """Represents a file prepared for upload."""
    file_path: str
    mime_type: str
    display_name: str
    is_vision_asset: bool = True
    gcs_uri: Optional[str] = None

@dataclass(frozen=True)
class FileOperationResult:
    """Encapsulates the result of a file operation (upload/delete)."""
    file_name: str
    success: bool
    gemini_file: Optional[types.File] = None
    error_message: Optional[str] = None

# --- Internal Helpers (Synchronous wrapper for Blocking I/O) ---

@retry(
    stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=settings.LLM_API_RETRY_WAIT_SECONDS, max=10),
    retry=retry_if_exception_type(RETRIABLE_EXCEPTIONS),
    reraise=True,
)
def _execute_blocking_upload(
    client: genai.Client, 
    path: str, 
    config: types.UploadFileConfig
) -> types.File:
    """Executes the blocking upload call with retry logic."""
    return client.files.upload(file=path, config=config)

@retry(
    stop=stop_after_attempt(settings.LLM_API_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=settings.LLM_API_RETRY_WAIT_SECONDS, max=10),
    retry=retry_if_exception_type(RETRIABLE_EXCEPTIONS),
    reraise=True,
)
def _execute_blocking_delete(client: genai.Client, file_name: str) -> None:
    """Executes the blocking delete call with retry logic."""
    client.files.delete(name=file_name)

def _sanitize_path(path: str) -> str:
    """Returns the basename of a path for logging to avoid PII leakage."""
    return os.path.basename(path)

# --- Public Async Interface ---

async def upload_single_file(
    client: genai.Client, 
    candidate: UploadCandidate,
    semaphore: asyncio.Semaphore
) -> FileOperationResult:
    """
    Uploads a single file to Gemini with concurrency control.
    Handles on-demand downloading from GCS if local file is missing but GCS URI is provided.

    Args:
        client: The Gemini API client.
        candidate: The file metadata object.
        semaphore: Asyncio semaphore to limit concurrency.

    Returns:
        FileOperationResult indicating success or failure.
    """
    safe_name = _sanitize_path(candidate.file_path)
    temp_file_path = None
    
    async with semaphore:
        try:
            target_path = candidate.file_path
            
            # If local path doesn't exist but we have a GCS URI, download it
            if not os.path.exists(target_path) and candidate.gcs_uri:
                logger.debug(f"Local file missing for {safe_name}. Downloading from {candidate.gcs_uri}...")
                
                # Create a temp file
                # We use mkstemp to ensure we have a valid path, but close the handle immediately
                fd, temp_file_path = tempfile.mkstemp(suffix=f"_{safe_name}")
                os.close(fd)
                
                await asyncio.to_thread(download_file_to_temp, candidate.gcs_uri, temp_file_path)
                target_path = temp_file_path
                logger.debug(f"Downloaded {safe_name} to {temp_file_path}")

            logger.debug(f"Starting upload for: {candidate.display_name} ({safe_name})")
            
            upload_config = types.UploadFileConfig(
                display_name=candidate.display_name,
                mime_type=candidate.mime_type,
            )

            # Offload blocking I/O to a thread
            uploaded_file = await asyncio.to_thread(
                _execute_blocking_upload, 
                client, 
                target_path, 
                upload_config
            )

            logger.info(f"Upload success: {candidate.display_name} -> {uploaded_file.uri}")
            return FileOperationResult(
                file_name=candidate.display_name,
                success=True,
                gemini_file=uploaded_file
            )

        except Exception as e:
            # We catch generic Exception here because the retry logic handled the specific ones.
            # If we are here, retries were exhausted or a non-retriable error occurred.
            error_msg = f"Upload failed for {candidate.display_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return FileOperationResult(
                file_name=candidate.display_name,
                success=False,
                error_message=error_msg
            )
        finally:
            # Cleanup temp file if we created one
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.debug(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")

async def upload_vision_files_batch(
    client: genai.Client, 
    files: Sequence[UploadCandidate]
) -> List[FileOperationResult]:
    """
    Uploads a batch of vision files to Gemini.

    Args:
        client: The Gemini API client.
        files: Sequence of UploadCandidate objects.

    Returns:
        List of FileOperationResult objects.
    """
    if not files:
        return []

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
    
    # Filter only vision assets if mixed types are passed
    # We relax the check: either file exists OR gcs_uri is present
    valid_candidates = [
        f for f in files 
        if f.is_vision_asset and (os.path.exists(f.file_path) or f.gcs_uri)
    ]
    
    if len(valid_candidates) < len(files):
        logger.warning(f"Skipped {len(files) - len(valid_candidates)} invalid or non-vision files.")

    tasks = [
        upload_single_file(client, candidate, semaphore) 
        for candidate in valid_candidates
    ]

    logger.info(f"Dispatching {len(tasks)} file uploads to Gemini.")
    results = await asyncio.gather(*tasks)
    
    return list(results)

async def delete_single_file(
    client: genai.Client, 
    file_name: str,
    semaphore: asyncio.Semaphore
) -> bool:
    """Deletes a single file with concurrency control."""
    async with semaphore:
        try:
            await asyncio.to_thread(_execute_blocking_delete, client, file_name)
            logger.debug(f"Deleted file: {file_name}")
            return True
        except google_exceptions.NotFound:
            logger.warning(f"File not found during deletion: {file_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete {file_name}: {e}", exc_info=True)
            return False

async def cleanup_uploaded_files(
    client: genai.Client, 
    file_names: List[str]
) -> tuple[int, int]:
    """
    Deletes multiple uploaded files from Gemini File Service.

    Returns:
        Tuple[int, int]: (successful_deletions, failed_deletions)
    """
    if not file_names:
        return 0, 0

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DELETES)
    tasks = [delete_single_file(client, name, semaphore) for name in file_names]

    logger.info(f"Cleaning up {len(tasks)} files from Gemini.")
    results = await asyncio.gather(*tasks)

    success_count = sum(results)
    fail_count = len(results) - success_count
    
    logger.info(f"Cleanup complete: {success_count} deleted, {fail_count} failed.")
    return success_count, fail_count
