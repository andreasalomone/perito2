import io
import logging
import os
from datetime import datetime
from typing import Tuple, Union

import click
from dotenv import load_dotenv
from flask import (
    Flask,
)
from flask import Response as FlaskResponse
from flask import (
    current_app,
    flash,
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
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.security import check_password_hash, generate_password_hash

import docx_generator
from admin.routes import admin_bp
from core import logging_config
from core.config import settings
from core.database import db
from services import db_service, report_service

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
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Basic Auth
auth = HTTPBasicAuth()
users = {settings.AUTH_USERNAME: generate_password_hash(settings.AUTH_PASSWORD)}


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


# Prometheus Metrics
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})

# --- Routes ---


@app.route("/", methods=["GET"])
@auth.login_required
def index() -> str:
    """Renders the index page."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute;20 per hour")
@auth.login_required
def upload_files() -> Union[str, FlaskResponse]:
    """
    Handles file uploads and report generation.
    Delegates logic to report_service.
    """
    files = request.files.getlist("files")
    redirect_url, rendered_template = report_service.handle_file_upload(
        files, app.root_path
    )

    if redirect_url:
        return redirect(redirect_url)
    if rendered_template:
        return rendered_template

    # Fallback (should not be reached if service handles all cases)
    return redirect(url_for("index"))


@app.route("/report/<int:report_id>", methods=["GET"])
@auth.login_required
def show_report(report_id: int) -> Union[str, FlaskResponse]:
    """Displays a previously generated report."""
    report_log = db_service.get_report_log(report_id)
    if not report_log or not report_log.final_report_text:
        flash("Report not found.", "error")
        return redirect(url_for("index"))

    return render_template(
        "report.html",
        report_content=report_log.final_report_text,
        filenames=[],
        generation_time=report_log.generation_time_seconds,
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

        # Fetch the report from the database using db_service
        report_log = db_service.get_report_log(report_log_id)

        if not report_log:
            current_app.logger.error(
                f"ReportLog with ID {report_log_id} not found in the database."
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
                f"Report content for ReportLog ID {report_log_id} is empty."
            )
            flash(
                "The report content is empty and cannot be downloaded. Please try generating it again.",
                "error",
            )
            return redirect(url_for("index"))

        current_app.logger.info(f"Generating DOCX for ReportLog ID {report_log_id}")

        # Run CPU-bound docx generation directly (WSGI workers handle concurrency)
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
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    with app.app_context():
        db.create_all()

    click.echo("Initialized the database.")


if __name__ == "__main__":
    app.run(debug=True)
