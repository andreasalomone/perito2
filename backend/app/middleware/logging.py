import contextlib
import logging
import time
from typing import Any, Callable, Dict, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CloudRunLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure every request is logged with GCP Trace Context.
    """

    # Paths to exclude from access logging to prevent noise
    SKIP_PATHS: Set[str] = {"/health", "/docs", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Check if path should be skipped
        if request.url.path in self.SKIP_PATHS:
            skipped_response: Response = await call_next(request)
            return skipped_response

        start_time = time.time()

        # 2. Extract Trace Context
        trace_header = request.headers.get("X-Cloud-Trace-Context", "")
        trace_id = None
        span_id = None

        if trace_header:
            with contextlib.suppress(Exception):
                # Header format: "TRACE_ID/SPAN_ID;o=TRACE_TRUE"
                parts = trace_header.split("/")
                if len(parts) > 0:
                    trace_id = parts[0]
                if len(parts) > 1:
                    span_id = parts[1].split(";")[0]
        # 3. Prepare Log Context
        log_context: Dict[str, Any] = {
            "http_method": request.method,
            "path": request.url.path,
            "trace_id": trace_id,
            "span_id": span_id,
        }

        try:
            response: Response = await call_next(request)

            # 4. Log Success
            process_time = (time.time() - start_time) * 1000
            log_context["status_code"] = response.status_code
            log_context["process_time_ms"] = round(process_time, 2)

            logger.info(
                f"Request finished: {request.method} {request.url.path}",
                extra=log_context,
            )
            return response

        except Exception as e:
            # 5. Log Exception (Critical for Error Reporting)
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra=log_context,
            )
            raise e
