import logging
import sys
import traceback
from typing import Any, Dict, List, Optional

from pythonjsonlogger import jsonlogger

# Assuming settings are importable; strict typing for the settings object is implied.
from app.core.config import settings


class GoogleCloudFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON Formatter optimized for Google Cloud Run (GCP).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optimization: Cache Project ID once at startup
        self.project_id = getattr(settings, "GOOGLE_CLOUD_PROJECT", None)

    def process_log_record(self, log_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mutates the log record to match GCP structured logging schemas.
        """
        # 1. Map Severity
        if "levelname" in log_record:
            log_record["severity"] = log_record.pop("levelname")

        # 2. Map Message
        if "msg" in log_record:
            log_record["message"] = log_record.pop("msg")

        # 3. Handle Exceptions for GCP Error Reporting
        if "exc_info" in log_record:
            exc_info = log_record.pop("exc_info")
            if exc_info and exc_info != "None":
                if isinstance(exc_info, tuple):
                    log_record["stack_trace"] = "".join(
                        traceback.format_exception(*exc_info)
                    )
                else:
                    log_record["stack_trace"] = str(exc_info)

        # 4. Trace Correlation (only if project_id is cached)
        if self.project_id:
            if "trace_id" in log_record:
                trace_id = log_record.pop("trace_id")
                if trace_id:
                    log_record["logging.googleapis.com/trace"] = (
                        f"projects/{self.project_id}/traces/{trace_id}"
                    )

            if "span_id" in log_record:
                log_record["logging.googleapis.com/spanId"] = log_record.pop("span_id")

        # 5. Source Location
        if "pathname" in log_record and "lineno" in log_record:
            log_record["logging.googleapis.com/sourceLocation"] = {
                "file": log_record.pop("pathname"),
                "line": str(log_record.pop("lineno")),
                "function": log_record.pop("funcName", "unknown"),
            }

        return log_record


def setup_logging(
    silence_loggers: Optional[List[str]] = None,
) -> logging.Logger:
    """
    Configures the root logger for structured JSON output on GCP.

    Args:
        silence_loggers: A list of logger names to set to WARNING level.
                         Defaults to a standard noisy list if None.

    Returns:
        logging.Logger: The configured root logger.
    """
    root_logger = logging.getLogger()

    # 1. Idempotency Check & Cleanup
    # Iterate over a copy to safely remove handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 2. Stream Handler (Standard Output)
    stream_handler = logging.StreamHandler(sys.stdout)

    # 3. JSON Formatter
    # We define the fields we initially extract from the LogRecord attributes.
    formatter = GoogleCloudFormatter(
        fmt="%(asctime)s %(levelname)s %(message)s %(name)s %(pathname)s %(lineno)s %(funcName)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # 4. Set Log Level
    # Fail safe to INFO if configuration is missing or invalid
    try:
        level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
        root_logger.setLevel(level_str)
    except (ValueError, TypeError):
        root_logger.setLevel(logging.INFO)

    # 5. Silence Noisy Third-Party Libraries
    if silence_loggers is None:
        silence_loggers = [
            "uvicorn.access",
            "uvicorn.error",
            "google.auth",
            "google.cloud",
            "urllib3",
        ]

    for logger_name in silence_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # 6. Final Verification Log
    # Using 'extra' to mimic how middleware might inject trace data
    logging.info(
        "📝 Logging initialized.",
        extra={
            "json_enabled": True,
            "log_level": logging.getLevelName(root_logger.level),
            "platform": "GCP",
        },
    )

    return root_logger
