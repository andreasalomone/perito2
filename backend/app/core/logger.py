import logging
import sys
from typing import Any, Dict, List

from pythonjsonlogger import jsonlogger

# We assume settings are available. In production, wrap this in a try/except
# or use a Pydantic BaseSettings object to guarantee existence.
from app.core.config import settings

class GoogleCloudFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON Formatter optimized for Google Cloud Run.
    Ensures fields map correctly to GCP Structured Logging entries.
    """
    
    def process_log_record(self, log_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Final pass to transform log record into GCP-compatible JSON.
        """
        # 1. Map 'levelname' to GCP 'severity'
        if "levelname" in log_record:
            log_record["severity"] = log_record.pop("levelname")
        
        # 2. Ensure 'message' field exists (GCP UI requirement)
        # python-json-logger sometimes leaves the message in 'message' or 'msg'
        if "msg" in log_record:
            log_record["message"] = log_record.pop("msg")
            
        return log_record

def setup_logging() -> logging.Logger:
    """
    Configures the root logger for structured JSON output.
    Idempotent: Safe to call multiple times, though typically called once at startup.
    
    Returns:
        logging.Logger: The configured root logger instance.
    """
    root_logger = logging.getLogger()
    
    # 1. Safe Handler Removal (Iterate over a copy of the list)
    # Prevents skipping handlers due to index shifts during removal.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 2. Stream Handler (Standard Output)
    # Cloud Run captures stdout/stderr automatically.
    stream_handler = logging.StreamHandler(sys.stdout)
    
    # 3. JSON Formatter Configuration
    # We define the specific fields we want to extract from the LogRecord.
    # Note: 'trace' and 'span_id' should be injected via Middleware/Extra
    formatter = GoogleCloudFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(exc_info)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ", # Strict ISO 8601 UTC
    )
    
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    
    # 4. Set Log Level safely
    try:
        log_level = settings.LOG_LEVEL.upper()
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            # Fallback to INFO if configuration is invalid
            log_level = "INFO" 
        root_logger.setLevel(log_level)
    except (AttributeError, ValueError):
        # Fallback if settings are malformed
        root_logger.setLevel(logging.INFO)

    # 5. Silence Noisy Third-Party Libraries
    # These libraries produce verbose logs that clutter GCP logs and increase costs.
    noisy_loggers: List[str] = [
        "uvicorn.access", # Handled by Cloud Run Load Balancer logs
        "uvicorn.error",
        "google.auth",    # Very verbose credential checks
        "google.cloud",
        "urllib3",
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Log a startup message to verify configuration
    logging.info(
        "📝 Logging initialized.", 
        extra={"configuration": "json", "environment": getattr(settings, "ENVIRONMENT", "UNKNOWN")}
    )
    
    return root_logger
