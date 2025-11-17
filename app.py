import asyncio
import io
import logging
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import click
from dotenv import load_dotenv
from flask import (
    Flask,
)
from flask import Response as FlaskResponse
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import document_processor
import docx_generator
import llm_handler
from admin.routes import admin_bp
from core.config import settings
from core.database import db
from core.models import DocumentLog, ReportLog, ReportStatus

load_dotenv()

app = Flask(__name__)

# --- App Configuration ---
# It's crucial to set a secret key for session management, used by the admin panel.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_fallback_secret_key")
app.config["SECRET_KEY"] = settings.FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

# --- Database Configuration ---
# Production check: Use DATABASE_URL from environment if available (for Render/Heroku),
# otherwise fall back to local SQLite for development.
database_uri = os.environ.get("DATABASE_URL")
if database_uri:
    # Ensure the URI uses the 'postgresql+psycopg' dialect to use the modern driver.
    if database_uri.startswith("postgres://"):
        database_uri = database_uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_uri.startswith("postgresql://"):
        database_uri = database_uri.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    database_uri or f"sqlite:///{os.path.join(app.instance_path, 'project.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)

# Register the admin blueprint
app.register_blueprint(admin_bp)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour", "5 per minute"],
    storage_uri="memory://",  # For single instance. For multi-instance, use Redis.
    # RATELIMIT_STRATEGY: 'fixed-window', # or 'moving-window'
)

auth = HTTPBasicAuth()

# Define users in environment variables for security
# In Render, set BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD
users = {
    os.environ.get("BASIC_AUTH_USERNAME", "admin"): generate_password_hash(
        os.environ.get("BASIC_AUTH_PASSWORD", "defaultpassword")
    )
}


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


# --- Logging Configuration ---
# Main application logging format that includes request_id
main_log_format = (
    "%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s"
)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format=main_log_format,
)  # Apply main format globally first

# Specific logger for startup messages, potentially before request_id is meaningful or filter is fully active
logger_for_startup = logging.getLogger("hypercorn_startup_test")
# If this logger only logs at startup, it might not need/have request_id.
# To avoid errors, give it a simple handler and formatter if it logs before the filter is guaranteed.
if (
    not logger_for_startup.handlers
):  # Add a specific handler if none exist (e.g. in some environments)
    startup_handler = logging.StreamHandler(sys.stderr)  # Log to stderr
    startup_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )  # No request_id
    startup_handler.setFormatter(startup_formatter)
    logger_for_startup.addHandler(startup_handler)
    logger_for_startup.propagate = (
        False  # Don't pass to root if we have a specific handler
    )

logger_for_startup.info(
    "Flask application starting up / reloaded by Hypercorn (via dedicated startup logger)."
)

# Configure httpx logger to be less verbose
logging.getLogger("httpx").setLevel(logging.WARNING)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        # Print directly to stderr to avoid recursion and bypass logging system for this debug
        # print(f"RequestIdFilter: ENTERED. Filtering record for logger '{record.name}'. Message: '{record.getMessage()[:70]}...'", file=sys.stderr)

        effective_request_id = "N/A_FILTER_DEFAULT_INIT"
        try:
            # g is imported at module level 'from flask import g'
            # Accessing g.get() outside of app/request context should raise RuntimeError
            # print(f"RequestIdFilter: DEBUG Attempting g.get for '{record.name}'", file=sys.stderr)
            effective_request_id = g.get("request_id", "N/A_FROM_G_GET_WITH_DEFAULT")
            # print(f"RequestIdFilter: DEBUG g.get succeeded for '{record.name}', effective_request_id: {effective_request_id}", file=sys.stderr)
        except RuntimeError:
            effective_request_id = "N/A_RUNTIME_ERROR"
            # print(f"RequestIdFilter: DEBUG RuntimeError for '{record.name}'", file=sys.stderr)
        except NameError:
            # This should ideally not happen if 'from flask import g' at module level is successful
            effective_request_id = "N/A_NAME_ERROR_G_NOT_FOUND"
            # print(f"RequestIdFilter: DEBUG NameError for '{record.name}'", file=sys.stderr)
        except Exception as e:
            # Catch any other unexpected exception during g.get() or related operations
            effective_request_id = f"N/A_UNEXPECTED_FILTER_ERR_{type(e).__name__}"
            # print(f"RequestIdFilter: DEBUG Unexpected Exception '{type(e).__name__}' for '{record.name}': {e}", file=sys.stderr)

        record.request_id = effective_request_id
        # print(f"RequestIdFilter: FINISHED. Set record.request_id to '{record.request_id}' for logger '{record.name}'", file=sys.stderr)
        return True


logger = logging.getLogger(__name__)

# Apply the filter to all handlers of the root logger
# This ensures that any logger (including Werkzeug's, if it uses the root handlers)
# will have its records passed through this filter before formatting.
_request_id_filter_instance = RequestIdFilter()
for handler in logging.root.handlers:
    handler.addFilter(_request_id_filter_instance)

# If the app-specific logger has its own handlers (not just propagating to root),
# and those handlers also use a format string with request_id,
# then uncommenting the line below for the app_logger might be necessary.
# However, typically basicConfig configures root, and app loggers propagate to root.
# logger.addFilter(_request_id_filter_instance) # Redundant if app logger propagates and root handlers have the filter.

# --- End Logging Configuration ---

# Define a directory for storing generated reports temporarily
REPORTS_DIR = os.path.join(tempfile.gettempdir(), "generated_reports_data")
os.makedirs(REPORTS_DIR, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in settings.ALLOWED_EXTENSIONS
    )


@app.before_request
def before_request_func():
    g.request_id = str(uuid.uuid4())
    logger.debug(f"Assigned request ID: {g.request_id} for {request.path}")


@app.route("/")
@auth.login_required
def index() -> str:
    logger.info(
        f"Accessing index route /. Request ID: {g.get('request_id', 'N/A_index')}"
    )
    return render_template("index.html")


# Helper Functions for upload_files
def _validate_file_list(files: List[FileStorage]) -> Optional[Tuple[str, str]]:
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


async def _process_single_file_storage(
    file_storage: FileStorage, temp_dir: str, current_total_extracted_text_length: int
) -> Tuple[List[Dict[str, Any]], int, List[Tuple[str, str]], Optional[str]]:
    """Processes a single FileStorage object, returning processed data, new text length, flash messages, and filename."""
    # Ensure g.request_id is available here if needed for deep logging
    # logger.debug(f"Processing single file. Request ID: {g.get('request_id', 'N/A_process_single')}")
    processed_entries: List[Dict[str, Any]] = []
    text_length_added_by_this_file = 0
    flash_messages: List[Tuple[str, str]] = []
    successfully_saved_filename: Optional[str] = None

    original_filename_for_logging = file_storage.filename or "<unknown>"

    # Individual file size check (re-check, as total size is checked before loop)
    # file_storage.seek(0, os.SEEK_END)
    # current_file_size = file_storage.tell()
    # file_storage.seek(0)
    # Note: The guide suggested checking file size here. However, the original code already has a robust check
    # for individual file size *before* this helper would be called (inside the main loop).
    # To avoid redundancy and keep this helper focused, we'll assume individual size check is done by the caller.
    # If not, it should be added here or, preferably, ensured by the caller.

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
        await asyncio.to_thread(file_storage.save, filepath)
        logger.info(f"Saved uploaded file to temporary path: {filepath}")
        successfully_saved_filename = filename  # Mark as saved for display list

        processed_info: Union[Dict[str, Any], List[Dict[str, Any]]] = (
            await asyncio.to_thread(
                document_processor.process_uploaded_file, filepath, temp_dir
            )
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


@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute;20 per hour")
@auth.login_required
async def upload_files() -> Union[str, FlaskResponse]:
    app_logger = logging.getLogger(__name__)
    app_logger.info(
        f"Entered /upload route. Request ID: {g.get('request_id', 'N/A_upload_entry')}"
    )

    # Step 1: Create a new ReportLog entry to track this entire process
    report_log = ReportLog()
    db.session.add(report_log)
    db.session.commit()
    app_logger.info(f"Created initial ReportLog entry with ID: {report_log.id}")

    if "files[]" not in request.files:
        flash("No file part in the request. Please select files to upload.", "error")
        report_log.status = ReportStatus.ERROR
        report_log.error_message = "No file part in the request."
        db.session.commit()
        return redirect(url_for("index"))

    files: List[FileStorage] = request.files.getlist("files[]")
    validation_error = _validate_file_list(files)
    if validation_error:
        flash(validation_error[0], validation_error[1])
        report_log.status = ReportStatus.ERROR
        report_log.error_message = validation_error[0]
        db.session.commit()
        return redirect(request.url)

    processed_file_data: List[Dict[str, Any]] = []
    uploaded_filenames_for_display: List[str] = []
    temp_dir: Optional[str] = None
    total_upload_size = 0
    current_total_extracted_text_length = 0

    try:
        # Calculate total upload size first
        for file_storage in files:
            if file_storage and file_storage.filename:
                file_storage.seek(0, os.SEEK_END)
                total_upload_size += file_storage.tell()
                file_storage.seek(0)

        if total_upload_size > settings.MAX_TOTAL_UPLOAD_SIZE_BYTES:
            error_msg = f"Total upload size exceeds the limit of {settings.MAX_TOTAL_UPLOAD_SIZE_MB} MB."
            logger.warning(f"{error_msg} ({total_upload_size} bytes)")
            flash(error_msg, "error")
            report_log.status = ReportStatus.ERROR
            report_log.error_message = error_msg
            db.session.commit()
            return redirect(request.url)

        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")

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
                # Log this skipped file as a document for traceability
                doc_log = DocumentLog(
                    report_id=report_log.id,
                    original_filename=file_storage.filename,
                    stored_filepath="SKIPPED_DUE_TO_SIZE",
                    file_size_bytes=current_file_size,
                )
                db.session.add(doc_log)
                continue

            entries, text_added, f_messages, saved_fname = (
                await _process_single_file_storage(
                    file_storage, temp_dir, current_total_extracted_text_length
                )
            )
            processed_file_data.extend(entries)
            current_total_extracted_text_length += text_added
            for fm in f_messages:
                flash(fm[0], fm[1])

            if saved_fname:
                uploaded_filenames_for_display.append(saved_fname)
                # Step 2: Create DocumentLog for the successfully processed file
                doc_log = DocumentLog(
                    report_id=report_log.id,
                    original_filename=file_storage.filename,
                    stored_filepath=os.path.join(
                        temp_dir, saved_fname
                    ),  # Store temp path for now
                    file_size_bytes=current_file_size,
                )
                db.session.add(doc_log)

        if not processed_file_data and not uploaded_filenames_for_display:
            flash("No files were suitable for processing.", "warning")
            report_log.status = ReportStatus.ERROR
            report_log.error_message = (
                "No files were suitable for processing after filtering."
            )
            db.session.commit()
            return redirect(url_for("index"))

        db.session.commit()  # Commit document logs before calling LLM

        # Step 3: Call LLM and update ReportLog with results
        start_time = datetime.utcnow()
        report_content: str = await llm_handler.generate_report_from_content(
            processed_files=processed_file_data, additional_text=""
        )
        end_time = datetime.utcnow()

        report_log.generation_time_seconds = (end_time - start_time).total_seconds()
        report_log.llm_raw_response = report_content
        report_log.final_report_text = report_content  # Initially the same

        if not report_content or report_content.strip().startswith("ERROR:"):
            logger.error(f"LLM Error: {report_content}")
            flash(f"Could not generate report: {report_content}", "error")
            report_log.status = ReportStatus.ERROR
            report_log.error_message = report_content
            db.session.commit()
            return render_template(
                "index.html", filenames=uploaded_filenames_for_display
            )

        # Success case
        report_log.status = ReportStatus.SUCCESS
        # TODO: Replace with actual cost from a modified llm_handler
        report_log.api_cost_usd = 0.03  # Placeholder value
        db.session.commit()

        # Store the report_log.id in the session for the next step (download)
        session["report_log_id"] = report_log.id

        return render_template(
            "report.html",
            report_content=report_content,
            filenames=uploaded_filenames_for_display,
            generation_time=report_log.generation_time_seconds,
        )

    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {e}", exc_info=True)
        flash("An unexpected server error occurred.", "error")
        report_log.status = ReportStatus.ERROR
        report_log.error_message = str(e)
        db.session.commit()
        return redirect(url_for("index"))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                # In a real scenario with permanent storage, you'd copy files out of temp_dir
                # before deleting it. For now, we accept the stored_filepath becomes invalid.
                await asyncio.to_thread(shutil.rmtree, temp_dir)
                logger.info(f"Successfully removed temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(
                    f"Error removing temporary directory {temp_dir}: {e}", exc_info=True
                )


# Add this new function somewhere after the /upload route in app.py


@app.route("/report")
@auth.login_required
def show_report():
    """
    Displays the generated report page by fetching data from the DB
    using the ID stored in the session.
    """
    report_log_id = session.get("report_log_id")

    if not report_log_id:
        flash(
            "Could not find a report to display. Please generate one first.", "warning"
        )
        return redirect(url_for("index"))

    report_log = db.session.get(ReportLog, report_log_id)

    if not report_log or report_log.status != ReportStatus.SUCCESS:
        flash(
            "The requested report was not found or was not successfully generated.",
            "error",
        )
        return redirect(url_for("index"))

    # You might need to fetch the original filenames again if you want to display them
    # For simplicity, we'll just pass the essential data.
    # To get filenames: docs = DocumentLog.query.filter_by(report_id=report_log.id).all()
    # filenames = [os.path.basename(doc.original_filename) for doc in docs]

    return render_template(
        "report.html",
        report_content=report_log.final_report_text or report_log.llm_raw_response,
        generation_time=report_log.generation_time_seconds,
        # filenames=filenames # Optional: if you need to display them
    )


@app.route("/download_report", methods=["POST"])
@limiter.limit("30 per minute")
@auth.login_required
def download_report() -> Union[FlaskResponse, Tuple[str, int]]:
    current_app.logger.info(
        f"Attempting to download report. Session active: {bool(session)}"
    )

    try:
        report_log_id = session.get("report_log_id")
        current_app.logger.debug(
            f"Retrieved report_log_id from session: {report_log_id}"
        )

        if not report_log_id:
            current_app.logger.error("Report log ID is missing in session.")
            flash(
                "Your session has expired or the report ID was lost. Please generate the report again.",
                "error",
            )
            return redirect(url_for("index"))

        # Fetch the report from the database
        report_log = db.session.get(ReportLog, report_log_id)

        if not report_log:
            current_app.logger.error(
                f"ReportLog with ID {report_log_id} not found in the database."
            )
            flash(
                "The requested report could not be found in the system. Please generate it again.",
                "error",
            )
            return redirect(url_for("index"))

        # Use the final_report_text if available (for future editing), otherwise the raw response
        report_content_from_db = (
            report_log.final_report_text or report_log.llm_raw_response
        )

        if not report_content_from_db:
            current_app.logger.error(
                f"Report content for ReportLog ID {report_log_id} is empty."
            )
            flash(
                "The report content is empty and cannot be downloaded. Please try generating it again.",
                "error",
            )
            return redirect(url_for("index"))

        current_app.logger.info(f"Generating DOCX for ReportLog ID {report_log_id}")
        file_stream: io.BytesIO = docx_generator.create_styled_docx(
            report_content_from_db
        )

        clean_company_name = "".join(
            c for c in session.get("company_name", "report") if c.isalnum() or c in " -"
        )
        download_display_filename = f"Perizia_{clean_company_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=download_display_filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        logger.error(f"Error generating DOCX: {e}", exc_info=True)
        flash(f"An error occurred while generating the DOCX file: {str(e)}", "error")
        return redirect(url_for("index"))


@app.cli.command("init-db")
def init_db_command():
    """Clear existing data and create new tables."""
    # Ensure the instance folder exists before creating the database
    try:
        os.makedirs(app.instance_path)
    except OSError:
        # The directory already exists, which is fine.
        pass

    with app.app_context():
        db.create_all()

    click.echo("Initialized the database.")


if __name__ == "__main__":
    app.run(debug=True)
