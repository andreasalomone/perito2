import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import flash, render_template, session, url_for
from werkzeug.datastructures import FileStorage

import llm_handler
from core.config import settings
from core.models import ReportStatus
from services import db_service, file_service

logger = logging.getLogger(__name__)


def handle_file_upload(
    files: List[FileStorage], upload_base_dir: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Orchestrates the file upload and report generation process.
    Returns a tuple (redirect_url, rendered_template).
    If redirect_url is set, the caller should redirect.
    If rendered_template is set, the caller should return it.
    """
    # Step 1: Create a new ReportLog entry
    report_log = db_service.create_initial_report_log()

    validation_error = file_service.validate_file_list(files)
    if validation_error:
        flash(validation_error[0], validation_error[1])
        db_service.update_report_status(
            report_log.id, ReportStatus.ERROR, error_message=validation_error[0]
        )
        return None, None  # Caller should handle redirect to request.url or index

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
            flash(error_msg, "error")
            db_service.update_report_status(
                report_log.id, ReportStatus.ERROR, error_message=error_msg
            )
            return None, None

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
                flash(
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

            entries, text_added, f_messages, saved_fname = (
                file_service.process_single_file_storage(
                    file_storage, temp_dir, current_total_extracted_text_length
                )
            )
            processed_file_data.extend(entries)
            current_total_extracted_text_length += text_added
            for fm in f_messages:
                flash(fm[0], fm[1])

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
            flash("No files were suitable for processing.", "warning")
            db_service.update_report_status(
                report_log.id,
                ReportStatus.ERROR,
                error_message="No files were suitable for processing after filtering.",
            )
            return url_for("index"), None

        # Call LLM
        start_time = datetime.utcnow()
        report_content: str = llm_handler.generate_report_from_content_sync(
            processed_files=valid_processed_data, additional_text=""
        )
        end_time = datetime.utcnow()

        generation_time = (end_time - start_time).total_seconds()

        if not report_content or report_content.strip().startswith("ERROR:"):
            logger.error(f"LLM Error: {report_content}")
            flash(f"Could not generate report: {report_content}", "error")
            db_service.update_report_status(
                report_log.id,
                ReportStatus.ERROR,
                error_message=report_content,
                llm_raw_response=report_content,
                generation_time_seconds=generation_time,
            )
            return None, render_template(
                "index.html", filenames=uploaded_filenames_for_display
            )

        db_service.update_report_status(
            report_log.id,
            ReportStatus.SUCCESS,
            llm_raw_response=report_content,
            final_report_text=report_content,
            generation_time_seconds=generation_time,
            api_cost_usd=0.03,
        )

        session["report_log_id"] = report_log.id

        return None, render_template(
            "report.html",
            report_content=report_content,
            filenames=uploaded_filenames_for_display,
            generation_time=generation_time,
        )

    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {e}", exc_info=True)
        flash("An unexpected server error occurred.", "error")
        if "report_log" in locals():
            db_service.update_report_status(
                report_log.id, ReportStatus.ERROR, error_message=str(e)
            )
        return url_for("index"), None
