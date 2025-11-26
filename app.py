import io
import logging
import os
import time
from datetime import datetime
from typing import Tuple, Union

import click
from dotenv import load_dotenv
from flask import Flask
from flask import Response as FlaskResponse
from flask import (
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from admin.routes import admin_bp
from core import logging_config
from core.config import settings
from core.database import db
from core.security import auth
from services import db_service, docx_generator, report_service

load_dotenv()

# --- Logging Configuration ---
logger = logging.getLogger(__name__)

# --- Flask App Setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = settings.FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

# Database Configuration
database_uri = settings.DATABASE_URL
if database_uri:
    if database_uri.startswith("postgres://"):
        database_uri = database_uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_uri.startswith("postgresql://"):
        database_uri = database_uri.replace("postgresql://", "postgresql+psycopg://", 1)

    # Add SSL mode if connecting to remote PostgreSQL and not already specified
    if "sslmode=" not in database_uri:
        separator = "&" if "?" in database_uri else "?"
        database_uri = f"{database_uri}{separator}sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = (
    database_uri or f"sqlite:///{os.path.join(app.instance_path, 'project.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)

# Register the admin blueprint
app.register_blueprint(admin_bp)

# Configure logging
logging_config.configure_logging(app)

# Rate Limiting
# Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri=settings.REDIS_URL or "memory://",
    strategy="fixed-window",
)

# Exempt static files from rate limiting
# Note: We need to do this after the app is created but before requests
with app.app_context():
    if "static" in app.view_functions:
        limiter.exempt(app.view_functions["static"])


# Prometheus Metrics
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})


# --- Request Logging Middleware ---
@app.before_request
def start_timer():
    g.start = time.time()


@app.after_request
def log_request(response):
    if request.path == "/favicon.ico":
        return response
    if request.path.startswith("/static"):
        return response

    now = time.time()
    duration = round(now - g.start, 4) if hasattr(g, "start") else 0
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    host = request.host.split(":", 1)[0]
    args = dict(request.args)

    log_params = [
        ("method", request.method),
        ("path", request.path),
        ("status", response.status_code),
        ("duration", duration),
        ("ip", ip),
        ("host", host),
        ("params", args),
    ]

    parts = []
    for name, value in log_params:
        part = f"{name}={value}"
        parts.append(part)

    line = " ".join(parts)
    # Use INFO level for successful requests, WARNING/ERROR for others if needed
    # But for general visibility, INFO is good.
    logger.info(line)

    return response


# --- Routes ---


@app.route("/healthz", methods=["GET", "HEAD"])
def health_check() -> FlaskResponse:
    """Health check endpoint for monitoring."""
    return jsonify({"status": "healthy"})


@app.route("/", methods=["GET"])
@auth.login_required
def index() -> str:
    """Renders the index page."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute;20 per hour")
@auth.login_required
def upload_files() -> Union[str, FlaskResponse, Tuple[dict, int]]:
    """
    Handles file uploads and report generation.
    Delegates logic to report_service.
    """
    files = request.files.getlist("files")
    # Async upload handling
    result = report_service.handle_file_upload_async(files, app.root_path)

    if result.success:
        # Store report_log_id in session for download functionality
        if result.data and "report_id" in result.data:
            session["report_log_id"] = result.data["report_id"]

        # Return JSON response with task_id for polling
        return jsonify(result.data), 202
    else:
        # Flash errors and return JSON error or render template (depending on how frontend handles it)
        # For now, let's assume frontend will handle JSON error or we can keep flashing for non-async fallback?
        # But the plan says "Update /upload to return JSON".
        # Let's return JSON error.
        for msg in result.messages:
            flash(msg.message, msg.category)
        return (
            jsonify(
                {
                    "error": "Upload failed",
                    "messages": [msg.message for msg in result.messages],
                }
            ),
            400,
        )


@app.route("/report/<report_id>", methods=["GET"])
@auth.login_required
def show_report(report_id: str) -> Union[str, FlaskResponse]:
    """Displays a previously generated report."""
    report_log = db_service.get_report_log(report_id)
    if not report_log or not report_log.final_report_text:
        flash("Report not found.", "error")
        return redirect(url_for("index"))

    return render_template(
        "report_success.html",
        report_id=report_id,
        generation_time=report_log.generation_time_seconds,
        api_cost_usd=report_log.api_cost_usd,
    )


@app.route("/report/status/<report_id>", methods=["GET"])
@limiter.limit("200 per hour")  # Higher limit for polling endpoint
@auth.login_required
def check_report_status(report_id: str) -> FlaskResponse:
    """Checks the status of a report generation."""
    report_log = db_service.get_report_log(report_id)
    if not report_log:
        return jsonify({"status": "error", "message": "Report not found"}), 404

    return jsonify(
        {
            "status": report_log.status.value,
            "report_id": report_log.id,
            "error": report_log.error_message,
            "progress_logs": report_log.progress_logs,
            "current_step": report_log.current_step,
        }
    )


@app.route("/download_report/<report_id>", methods=["GET", "POST"])
@limiter.limit("30 per minute")
@auth.login_required
def download_report(report_id: str) -> Union[FlaskResponse, Tuple[str, int]]:
    current_app.logger.info(f"Attempting to download report: {report_id}")

    try:
        # Fetch the report from the database using db_service
        report_log = db_service.get_report_log(report_id)

        if not report_log:
            current_app.logger.error(
                f"ReportLog with ID {report_id} not found in the database."
            )
            flash(
                "The requested report could not be found in the system. Please generate it again.",
                "error",
            )
            return redirect(url_for("index"))

        # Use the final_report_text if available, otherwise the raw response
        report_content_from_db = (
            report_log.final_report_text or report_log.llm_raw_response
        )

        if not report_content_from_db:
            current_app.logger.error(
                f"Report content for ReportLog ID {report_id} is empty."
            )
            flash(
                "The report content is empty and cannot be downloaded. Please try generating it again.",
                "error",
            )
            return redirect(url_for("index"))

        current_app.logger.info(f"Generating DOCX for ReportLog ID {report_id}")

        # Run CPU-bound docx generation directly (WSGI workers handle concurrency)
        file_stream: io.BytesIO = docx_generator.create_styled_docx(
            report_content_from_db
        )

        # Clean company name for filename (if available in session, else generic)
        # Note: Session might not have the correct company name if multiple tabs are used,
        # but filename is less critical than content.
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
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    with app.app_context():
        db.create_all()

    click.echo("Initialized the database.")


if __name__ == "__main__":
    app.run(debug=True)
