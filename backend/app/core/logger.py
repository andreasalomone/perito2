import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings

def setup_logging():
    """
    Configures the root logger to output JSON formatted logs.
    This is essential for Google Cloud Logging to parse fields correctly.
    """
    logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in logger.handlers:
        logger.removeHandler(handler)
        
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Define JSON format
    # We include timestamp, level, name, message, and any extra fields
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        rename_fields={"asctime": "timestamp", "levelname": "severity"}
    )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Set log level from config
    logger.setLevel(settings.LOG_LEVEL.upper())
    
    # Quiet down some noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("google.cloud").setLevel(logging.WARNING)
    
    return logger
