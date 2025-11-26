import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import session
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import llm_handler
from core.config import settings
from core.models import ReportStatus
from core.service_result import ServiceResult
from services import db_service, file_service

# Import tasks lazily to avoid circular imports if necessary, or use string reference if possible
# But here we need to call .delay(), so we need the task object.
# To avoid circular import (app -> report_service -> tasks -> app), we rely on tasks importing app inside the function.
from services.tasks import generate_report_task

logger = logging.getLogger(__name__)


def handle_file_upload(files: List[FileStorage], upload_base_dir: str) -> ServiceResult:
    """
    Orchestrates the file upload and report generation process.
    Returns a ServiceResult.
    """
    result = ServiceResult(success=True)
    # Step 1: Create a new ReportLog entry
    report_log = db_service.create_initial_report_log()

    validation_result = file_service.validate_file_list(files)
    if not validation_result.success:
        for msg in validation_result.messages:
            result.add_message(msg.message, msg.category)

        # Assuming the first message is the main error for DB logging
        error_msg = (
            validation_result.messages[0].message
            if validation_result.messages
            else "Validation failed"
        )
        db_service.update_report_status(
            report_log.id, ReportStatus.ERROR, error_message=error_msg
        )
        result.success = False
        return result

    processed_file_data: List[Dict[str, Any]] = []
    uploaded_filenames_for_display: List[str] = []
    temp_dir: Optional[str] = None
    total_upload_size = 0
    current_total_extracted_text_length = 0

    try:
        # Calculate total upload size
        for file_storage in files:
            if file_storage and file_storage.filename:
                file_storage.seek(0, os.SEEK_END)
                total_upload_size += file_storage.tell()
                file_storage.seek(0)

        if total_upload_size > settings.MAX_TOTAL_UPLOAD_SIZE_BYTES:
            error_msg = f"Total upload size exceeds the limit of {settings.MAX_TOTAL_UPLOAD_SIZE_MB} MB."
            logger.warning(f"{error_msg} ({total_upload_size} bytes)")
            result.add_message(error_msg, "error")
            db_service.update_report_status(
                report_log.id, ReportStatus.ERROR, error_message=error_msg
            )
            result.success = False
            return result

        # Create persistent directory
        today_str = datetime.now().strftime("%Y/%m/%d")
        upload_session_dir = os.path.join(upload_base_dir, today_str, str(uuid.uuid4()))
        os.makedirs(upload_session_dir, exist_ok=True)
        temp_dir = upload_session_dir
        logger.info(f"Created persistent upload directory: {temp_dir}")

        for file_storage in files:
            if not file_storage or not file_storage.filename:
                continue

            start_pos = file_storage.tell()
            file_storage.seek(0, os.SEEK_END)
            current_file_size = file_storage.tell()
            file_storage.seek(start_pos)

            if current_file_size > settings.MAX_FILE_SIZE_BYTES:
                result.add_message(
                    f"File {file_storage.filename} exceeds the size limit of {settings.MAX_FILE_SIZE_MB} MB and was skipped.",
                    "warning",
                )
                db_service.create_document_log(
                    report_id=report_log.id,
                    original_filename=file_storage.filename,
                    stored_filepath="SKIPPED_DUE_TO_SIZE",
                    file_size_bytes=current_file_size,
                )
                continue

            file_result = file_service.process_single_file_storage(
                file_storage, temp_dir, current_total_extracted_text_length
            )

            entries = file_result.data.get("processed_entries", [])
            text_added = file_result.data.get("text_length_added", 0)
            saved_fname = file_result.data.get("saved_filename")

            processed_file_data.extend(entries)
            current_total_extracted_text_length += text_added

            for msg in file_result.messages:
                result.add_message(msg.message, msg.category)

            if saved_fname:
                uploaded_filenames_for_display.append(saved_fname)
                db_service.create_document_log(
                    report_id=report_log.id,
                    original_filename=file_storage.filename,
                    stored_filepath=os.path.join(temp_dir, saved_fname),
                    file_size_bytes=current_file_size,
                )

        # Filter out error and unsupported entries from processed_file_data before LLM
        valid_processed_data = [
            entry
            for entry in processed_file_data
            if entry.get("type") not in ["error", "unsupported"]
        ]

        if not valid_processed_data and not uploaded_filenames_for_display:
            result.add_message("No files were suitable for processing.", "warning")
            db_service.update_report_status(
                report_log.id,
                ReportStatus.ERROR,
                error_message="No files were suitable for processing after filtering.",
            )
            result.success = False
            return result

        # Call LLM
        start_time = datetime.utcnow()
        report_content, api_cost_usd, token_usage = (
            llm_handler.generate_report_from_content_sync(
                processed_files=valid_processed_data, additional_text=""
            )
        )
        end_time = datetime.utcnow()

        generation_time = (end_time - start_time).total_seconds()

        if not report_content or report_content.strip().startswith("ERROR:"):
            logger.error(f"LLM Error: {report_content}")
            result.add_message(f"Could not generate report: {report_content}", "error")
            db_service.update_report_status(
                report_log.id,
                ReportStatus.ERROR,
                error_message=report_content,
                llm_raw_response=report_content,
                generation_time_seconds=generation_time,
                api_cost_usd=api_cost_usd,
                prompt_token_count=token_usage.get("prompt_token_count"),
                candidates_token_count=token_usage.get("candidates_token_count"),
                total_token_count=token_usage.get("total_token_count"),
                cached_content_token_count=token_usage.get(
                    "cached_content_token_count"
                ),
            )
            result.success = False
            # Even on error, we might want to return filenames if we want to show them
            result.data = {"filenames": uploaded_filenames_for_display}
            return result

        db_service.update_report_status(
            report_log.id,
            ReportStatus.SUCCESS,
            llm_raw_response=report_content,
            final_report_text=report_content,
            generation_time_seconds=generation_time,
            api_cost_usd=api_cost_usd,
            prompt_token_count=token_usage.get("prompt_token_count"),
            candidates_token_count=token_usage.get("candidates_token_count"),
            total_token_count=token_usage.get("total_token_count"),
            cached_content_token_count=token_usage.get("cached_content_token_count"),
        )

        session["report_log_id"] = report_log.id

        result.data = {
            "report_content": report_content,
            "filenames": uploaded_filenames_for_display,
            "generation_time": generation_time,
        }
        return result

    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {e}", exc_info=True)
        result.add_message("An unexpected server error occurred.", "error")
        if "report_log" in locals():
            db_service.update_report_status(
                report_log.id, ReportStatus.ERROR, error_message=str(e)
            )
        result.success = False
        return result


def handle_file_upload_async(
    files: List[FileStorage], app_root_path: str
) -> ServiceResult:
    """
    Handles file upload asynchronously.
    Validates files, saves them, creates a report entry, and triggers a Celery task.
    """
    result = ServiceResult(success=True)

    # Validate files
    validation_result = file_service.validate_file_list(files)
    if not validation_result.success:
        return validation_result

    # Create initial ReportLog entry
    try:
        report_log = db_service.create_initial_report_log()
    except Exception as e:
        logger.error(f"Failed to create report log: {e}", exc_info=True)
        result.success = False
        result.add_message("Database error while initializing report.", "error")
        return result

    # Create a temporary directory for this report's files
    # We use the report ID to ensure uniqueness and easier cleanup
    temp_dir = os.path.join(settings.UPLOAD_FOLDER, str(report_log.id))
    os.makedirs(temp_dir, exist_ok=True)

    saved_file_paths = []
    original_filenames = []
    document_log_ids = []

    try:
        # Validate extensions and sizes before saving
        for file in files:
            if not file or not file.filename:
                continue

            # Check file extension
            if not file_service.allowed_file(file.filename):
                result.add_message(
                    f"File type not allowed for {file.filename}. Skipping.", "warning"
                )
                continue

            # Check file size
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning

            if file_size > settings.MAX_FILE_SIZE_BYTES:
                result.add_message(
                    f"File {file.filename} exceeds size limit ({settings.MAX_FILE_SIZE_MB} MB). Skipping.",
                    "warning",
                )
                continue

            filename = secure_filename(file.filename)
            if not filename:
                continue

            filepath = os.path.join(temp_dir, filename)
            file.save(filepath)
            saved_file_paths.append(filepath)
            original_filenames.append(file.filename)

            # Log document in DB
            doc_log = db_service.create_document_log(
                report_id=report_log.id,
                original_filename=file.filename,
                stored_filepath=filepath,
                file_size_bytes=os.path.getsize(filepath),
            )
            document_log_ids.append(doc_log.id)

        if not saved_file_paths:
            result.success = False
            result.add_message("No valid files were saved.", "error")
            db_service.update_report_status(
                report_log.id, ReportStatus.ERROR, error_message="No files saved."
            )
            return result

        # Trigger Celery task
        task = generate_report_task.delay(
            report_log.id, saved_file_paths, original_filenames, document_log_ids
        )

        result.data = {
            "task_id": task.id,
            "report_id": report_log.id,
            "status": "processing",
        }
        result.add_message("Files uploaded successfully. Processing started.", "info")

    except Exception as e:
        logger.error(f"Error in handle_file_upload_async: {e}", exc_info=True)
        result.success = False
        result.add_message("An unexpected error occurred during upload.", "error")
        db_service.update_report_status(
            report_log.id, ReportStatus.ERROR, error_message=str(e)
        )

    return result
