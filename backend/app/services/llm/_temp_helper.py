import logging
from typing import Any, Optional

from google import genai

types = genai.types
logger = logging.getLogger(__name__)


def _validate_candidate_finish_reason(
    candidate: Any, report_content: str
) -> Optional[str]:
    """Validates the finish reason of a response candidate."""
    if not candidate or not candidate.finish_reason:
        return None

    finish_reason_obj = candidate.finish_reason
    finish_reason_name = (
        finish_reason_obj.name
        if hasattr(finish_reason_obj, "name")
        else str(finish_reason_obj)
    )

    # Critical: Fail on MAX_TOKENS even if we have partial text
    if finish_reason_name == types.FinishReason.MAX_TOKENS.name:
        logger.warning("Content generation stopped due to MAX_TOKENS.")
        return "Error: Content generation reached maximum token limit. The generated text may be incomplete."

    elif finish_reason_name != types.FinishReason.STOP.name:
        logger.error(f"Content generation stopped for reason: {finish_reason_name}.")
        return f"Error: LLM generation stopped for reason: {finish_reason_name}."

    elif not report_content:
        logger.warning(
            "LLM generation finished (STOP), but no text content was extracted."
        )
        return "Error: LLM generation completed, but no usable text was found in the response."

    return None
