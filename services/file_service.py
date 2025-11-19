import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import document_processor
from core.config import settings

logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in settings.ALLOWED_EXTENSIONS
    )


def validate_file_list(files: List[FileStorage]) -> Optional[Tuple[str, str]]:
    """Validates the list of files to be uploaded."""
    if not files or all(f.filename == "" for f in files):
        logger.info("No files selected for uploading.")
        return "No files selected for uploading.", "warning"
    return None


def _add_text_data_to_processed_list(
    processed_file_data_list: List[Dict[str, Any]],
    current_total_length: int,
    text_content: str,
    filename: str,
    source_description: str,
) -> Tuple[List[Dict[str, Any]], int, Optional[Tuple[str, str]]]:
    """Helper to add extracted text to the list, handling truncation and size limits."""
    flash_message = None
    available_chars = settings.MAX_EXTRACTED_TEXT_LENGTH - current_total_length
    if available_chars <= 0:
        logger.warning(
            f"Maximum total extracted text length reached before processing content from {filename} ({source_description}). Skipping."
        )
        flash_message = (
            f"Skipped some content from {filename} ({source_description}) as maximum total text limit was reached.",
            "warning",
        )
        return processed_file_data_list, current_total_length, flash_message

    if len(text_content) > available_chars:
        text_content = text_content[:available_chars]
        logger.warning(
            f"Truncated text from {filename} ({source_description}) to fit within MAX_EXTRACTED_TEXT_LENGTH."
        )
        flash_message = (
            f"Content from {filename} ({source_description}) was truncated to fit the overall text limit.",
            "warning",
        )

    processed_file_data_list.append(
        {
            "type": "text",
            "filename": filename,
            "content": text_content,
            "source": source_description,
        }
    )
    current_total_length += len(text_content)
    return processed_file_data_list, current_total_length, flash_message


def process_single_file_storage(
    file_storage: FileStorage, temp_dir: str, current_total_extracted_text_length: int
) -> Tuple[List[Dict[str, Any]], int, List[Tuple[str, str]], Optional[str]]:
    """Processes a single FileStorage object, returning processed data, new text length, flash messages, and filename."""
    processed_entries: List[Dict[str, Any]] = []
    text_length_added_by_this_file = 0
    flash_messages: List[Tuple[str, str]] = []
    successfully_saved_filename: Optional[str] = None

    original_filename_for_logging = file_storage.filename or "<unknown>"

    if not allowed_file(original_filename_for_logging):
        logger.warning(
            f"File type not allowed: {original_filename_for_logging}, skipping."
        )
        flash_messages.append(
            (
                f"File type not allowed for {original_filename_for_logging}. It has been skipped.",
                "warning",
            )
        )
        processed_entries.append(
            {
                "type": "unsupported",
                "filename": original_filename_for_logging,
                "message": "File type not allowed",
            }
        )
        return (
            processed_entries,
            text_length_added_by_this_file,
            flash_messages,
            successfully_saved_filename,
        )

    filename = secure_filename(original_filename_for_logging)
    if not filename:
        logger.warning(
            f"secure_filename resulted in empty filename for original: {original_filename_for_logging}, skipping."
        )
        flash_messages.append(
            ("A file with an invalid name was skipped after securing.", "warning")
        )
        processed_entries.append(
            {
                "type": "error",
                "filename": original_filename_for_logging,
                "message": "Invalid filename after securing.",
            }
        )
        return (
            processed_entries,
            text_length_added_by_this_file,
            flash_messages,
            successfully_saved_filename,
        )

    filepath = os.path.join(temp_dir, filename)

    try:
        file_storage.save(filepath)
        logger.info(f"Saved uploaded file to temporary path: {filepath}")
        successfully_saved_filename = filename  # Mark as saved for display list

        processed_info: Union[Dict[str, Any], List[Dict[str, Any]]] = (
            document_processor.process_uploaded_file(filepath, temp_dir)
        )

        parts_to_process: List[Dict[str, Any]] = []
        was_eml = isinstance(processed_info, list)
        if was_eml:
            # It's an EML file that returned a list of its parts
            if processed_info:
                parts_to_process.extend(processed_info)
        elif isinstance(processed_info, dict):
            # It's any other single file type
            parts_to_process.append(processed_info)

        temp_processed_file_data_list_for_this_file: List[Dict[str, Any]] = []
        current_length_for_this_file_processing = current_total_extracted_text_length

        for part in parts_to_process:
            part_type = part.get("type")
            part_filename = part.get("filename", original_filename_for_logging)

            if part_type in ["error", "unsupported"]:
                processed_entries.append(part)
            elif part_type == "text" and part.get("content"):
                source_desc = (
                    f"from {original_filename_for_logging}"
                    if was_eml
                    else "file content"
                )

                (
                    temp_processed_file_data_list_for_this_file,
                    current_length_for_this_file_processing,
                    flash_msg,
                ) = _add_text_data_to_processed_list(
                    temp_processed_file_data_list_for_this_file,
                    current_length_for_this_file_processing,
                    part["content"],
                    part_filename,
                    source_desc,
                )
                if flash_msg:
                    flash_messages.append(flash_msg)

            elif part_type == "vision":
                processed_entries.append(part)

        # Add text data accumulated for this file to the main processed_entries
        processed_entries.extend(temp_processed_file_data_list_for_this_file)
        # Calculate how much new text length was actually added by this file's content
        text_length_added_by_this_file = (
            current_length_for_this_file_processing
            - current_total_extracted_text_length
        )

    except Exception as e:
        logger.error(f"Error saving or processing file {filename}: {e}", exc_info=True)
        flash_messages.append(
            (
                f"An unexpected error occurred while processing file {filename}. It has been skipped. Please check logs for details.",
                "error",
            )
        )
        processed_entries.append(
            {
                "type": "error",
                "filename": filename,
                "message": "An unexpected error occurred during processing. Please see logs.",
            }
        )

    return (
        processed_entries,
        text_length_added_by_this_file,
        flash_messages,
        successfully_saved_filename,
    )
