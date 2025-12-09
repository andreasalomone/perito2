import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.core.config import settings
from app.core.service_result import ServiceMessage, ServiceResult

from . import document_processor

logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    """
    Checks if the file extension is allowed based on settings.
    Uses os.path.splitext for robust extension extraction.
    """
    if not filename or "." not in filename:
        return False

    # Secure extraction of extension (e.g., 'image.jpg' -> '.jpg')
    _, ext = os.path.splitext(filename)
    return ext.lower() in settings.ALLOWED_MIME_TYPES


def validate_file_list(files: List[FileStorage]) -> ServiceResult:
    """Validates the list of files to be uploaded."""
    result = ServiceResult(success=True)
    if not files or all(f.filename == "" for f in files):
        logger.info("No files selected for uploading.")
        result.success = False
        result.add_message("No files selected for uploading.", "warning")
    return result


def _add_text_data_to_processed_list(
    processed_file_data_list: List[Dict[str, Any]],
    current_total_length: int,
    text_content: str,
    filename: str,
    source_description: str,
) -> Tuple[List[Dict[str, Any]], int, Optional[ServiceMessage]]:
    """
    Helper to add extracted text to the list, handling truncation and size limits.

    Structure of dict added to list:
    {
        "type": "text",
        "filename": str,
        "content": str,
        "source": str
    }
    """
    service_message = None
    available_chars = settings.MAX_EXTRACTED_TEXT_LENGTH - current_total_length

    if available_chars <= 0:
        logger.warning(
            f"Maximum total extracted text length reached before processing {filename}. Skipping."
        )
        service_message = ServiceMessage(
            f"Skipped content from {filename} (quota exceeded).",
            "warning",
        )
        return processed_file_data_list, current_total_length, service_message

    final_content = text_content
    if len(text_content) > available_chars:
        final_content = text_content[:available_chars]
        logger.warning(
            f"Truncated text from {filename} to fit MAX_EXTRACTED_TEXT_LENGTH."
        )
        service_message = ServiceMessage(
            f"Content from {filename} was truncated to fit the overall text limit.",
            "warning",
        )

    processed_file_data_list.append(
        {
            "type": "text",
            "filename": filename,
            "content": final_content,
            "source": source_description,
        }
    )
    current_total_length += len(final_content)
    return processed_file_data_list, current_total_length, service_message


def process_file_from_path(
    filepath: str, original_filename: str, current_total_extracted_text_length: int
) -> ServiceResult:
    """
    Processes a file from a given path.
    Expected to be called within a synchronous context (or wrapped via asyncio.to_thread).
    """
    processed_entries: List[Dict[str, Any]] = []
    text_length_added_by_this_file = 0
    result = ServiceResult(success=True)

    try:
        # Assumes document_processor.process_uploaded_file is synchronous
        processed_parts = document_processor.process_uploaded_file(
            filepath, os.path.dirname(filepath)
        )

        current_length_for_this_file = current_total_extracted_text_length

        for part in processed_parts:
            part_type = part.get("type")
            part_filename = part.get("filename", original_filename)

            if part_type == "text" and part.get("content"):
                source_desc = f"from {original_filename}"
                (
                    processed_entries_list,
                    current_length_for_this_file,
                    svc_msg,
                ) = _add_text_data_to_processed_list(
                    [],  # Temp list
                    current_length_for_this_file,
                    part["content"],
                    part_filename,
                    source_desc,
                )
                processed_entries.extend(processed_entries_list)
                if svc_msg:
                    result.messages.append(svc_msg)

            elif part_type in [
                "vision",
                "error",
                "unsupported",
                "attachment_reference",
            ]:
                processed_entries.append(part)

        text_length_added_by_this_file = (
            current_length_for_this_file - current_total_extracted_text_length
        )

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        logger.error(f"Error processing file {original_filename}: {e}", exc_info=True)
        result.add_message(
            f"An unexpected error occurred while processing {original_filename}.",
            "error",
        )
        processed_entries.append(
            {
                "type": "error",
                "filename": original_filename,
                "message": "An unexpected error occurred during processing.",
            }
        )

    result.data = {
        "processed_entries": processed_entries,
        "text_length_added": text_length_added_by_this_file,
    }
    return result


def process_single_file_storage(
    file_storage: FileStorage, temp_dir: str, current_total_extracted_text_length: int
) -> ServiceResult:
    """
    Processes a single FileStorage object with UUID isolation to prevent race conditions.
    """
    result = ServiceResult(success=True)
    original_filename = file_storage.filename or "unknown"

    # 1. Validation
    if not allowed_file(original_filename):
        logger.warning(f"File type not allowed: {original_filename}")
        result.add_message(f"File type not allowed for {original_filename}.", "warning")
        result.data = {
            "processed_entries": [
                {
                    "type": "unsupported",
                    "filename": original_filename,
                    "message": "File type not allowed",
                }
            ],
            "text_length_added": 0,
            "saved_filename": None,
        }
        return result

    # 2. Secure Filename
    filename = secure_filename(original_filename)
    if not filename:
        result.add_message(f"Invalid filename for {original_filename}.", "warning")
        result.data = {
            "processed_entries": [
                {
                    "type": "error",
                    "filename": original_filename,
                    "message": "Invalid filename.",
                }
            ],
            "text_length_added": 0,
            "saved_filename": None,
        }
        return result

    # 3. Isolation (UUID Subdirectory)
    # Creates /tmp/base_dir/<uuid>/filename.ext
    unique_subdir = os.path.join(temp_dir, str(uuid.uuid4()))
    os.makedirs(unique_subdir, exist_ok=True)

    filepath = os.path.join(unique_subdir, filename)
    successfully_saved_filename = None

    try:
        file_storage.save(filepath)
        logger.info(f"Saved file to isolated path: {filepath}")
        successfully_saved_filename = filename

        # 4. Processing
        process_result = process_file_from_path(
            filepath, original_filename, current_total_extracted_text_length
        )

        result.messages.extend(process_result.messages)
        result.data = process_result.data
        result.data["saved_filename"] = successfully_saved_filename

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        logger.error(f"Error handling file {filename}: {e}", exc_info=True)
        result.add_message(
            f"An unexpected error occurred while saving {filename}.",
            "error",
        )
        result.data = {
            "processed_entries": [
                {
                    "type": "error",
                    "filename": filename,
                    "message": "An unexpected error occurred during saving.",
                }
            ],
            "text_length_added": 0,
            "saved_filename": None,
        }

    finally:
        # 5. Cleanup
        # Gold Standard: Always clean up the UUID directory, regardless of success/failure
        if os.path.exists(unique_subdir):
            try:
                shutil.rmtree(unique_subdir)
                logger.debug(f"Cleaned up isolated temp dir: {unique_subdir}")
            except OSError as e:
                logger.warning(f"Failed to cleanup temp dir {unique_subdir}: {e}")

    return result
