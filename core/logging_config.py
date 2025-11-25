import logging
import sys

from flask import g

from core.config import settings


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        effective_request_id = "N/A_FILTER_DEFAULT_INIT"
        try:
            effective_request_id = g.get("request_id", "N/A_FROM_G_GET_WITH_DEFAULT")
        except RuntimeError:
            effective_request_id = "N/A_RUNTIME_ERROR"
        except NameError:
            effective_request_id = "N/A_NAME_ERROR_G_NOT_FOUND"
        except Exception as e:
            effective_request_id = f"N/A_UNEXPECTED_FILTER_ERR_{type(e).__name__}"

        record.request_id = effective_request_id
        return True


def configure_logging(app):
    # Main application logging format that includes request_id
    main_log_format = (
        "%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=main_log_format,
    )

    # Specific logger for startup messages
    logger_for_startup = logging.getLogger("hypercorn_startup_test")
    if not logger_for_startup.handlers:
        startup_handler = logging.StreamHandler(sys.stderr)
        startup_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        startup_handler.setFormatter(startup_formatter)
        logger_for_startup.addHandler(startup_handler)
        logger_for_startup.propagate = False

    logger_for_startup.info(
        "Flask application starting up / reloaded by Hypercorn (via dedicated startup logger)."
    )

    # Configure httpx logger to be less verbose
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Apply the filter to all handlers of the root logger
    _request_id_filter_instance = RequestIdFilter()
    for handler in logging.root.handlers:
        handler.addFilter(_request_id_filter_instance)

    # Integration with Gunicorn
    # If running under Gunicorn, wire up the app logger to Gunicorn's error log
    gunicorn_logger = logging.getLogger("gunicorn.error")
    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
        # Also set the root logger level to match gunicorn's level
        logging.getLogger().setLevel(gunicorn_logger.level)

