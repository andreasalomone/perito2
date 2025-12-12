"""Response parser service for parsing and validating LLM responses."""

import logging
from typing import Any, List, Optional

from google.genai import types

logger = logging.getLogger(__name__)


def extract_text_from_response(response: Any) -> str:
    """Extracts text content from an LLM response.

    Args:
        response: The LLM response object.

    Returns:
        Extracted text content, or empty string if not found.
    """
    report_content: str = ""

    try:
        if response.text:
            report_content = response.text
        elif response.candidates:
            parts_text: List[str] = []
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    parts_text.extend(
                        part.text
                        for part in candidate.content.parts
                        if hasattr(part, "text") and part.text is not None
                    )
            if parts_text:
                report_content = "".join(parts_text)
    except AttributeError as e:
        logger.warning(
            f"AttributeError while accessing response text or parts: {e}.",
            exc_info=True,
        )

    return report_content


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


def validate_response_content(response: Any, report_content: str) -> Optional[str]:
    """Validates LLM response content and checks for errors.

    Args:
        response: The LLM response object.
        report_content: The extracted text content.

    Returns:
        Error message if validation fails, None if valid.
    """
    # 1. Check for global blocking (Prompt Feedback)
    if response.prompt_feedback and response.prompt_feedback.block_reason:
        block_reason_obj = response.prompt_feedback.block_reason
        block_reason_name = (
            block_reason_obj.name
            if hasattr(block_reason_obj, "name")
            else str(block_reason_obj)
        )
        logger.error(
            f"Content generation blocked. Reason from prompt_feedback: {block_reason_name}"
        )
        return (
            f"Error: Content generation blocked by the LLM. Reason: {block_reason_name}"
        )

    # 2. Check Candidate Finish Reasons
    if response.candidates:
        if error := _validate_candidate_finish_reason(
            response.candidates[0], report_content
        ):
            return error

    elif not response.prompt_feedback:
        logger.error(
            "No candidates found in LLM response and not blocked by prompt_feedback."
        )
        return "Error: Unknown issue with LLM response, no candidates returned."

    # 4. Final check for empty content if everything else looked okay
    if not report_content:
        logger.error(
            f"Unknown issue: No text in Gemini response. Prompt Feedback: {response.prompt_feedback}. Candidate 0 Finish Reason (if any): {response.candidates[0].finish_reason if response.candidates and response.candidates[0] else 'N/A'}"
        )
        return "Error: Unknown issue with LLM response, no text content received."

    return None


def parse_llm_response(response: Any) -> str:
    """Parses and validates an LLM response.

    Args:
        response: The LLM response object.

    Returns:
        The extracted report content.

    Raises:
        ValueError: If validation fails (e.g. Max Tokens, Blocked, No Content).
    """
    report_content = extract_text_from_response(response)
    if error_message := validate_response_content(response, report_content):
        # LOGIC FIX: Fail hard if generation was incomplete/blocked.
        # This allows the caller loop to catch the exception and mark the case as ERROR.
        logger.error(f"Response validation failed: {error_message}")
        raise ValueError(error_message)

    logger.info("Report content successfully generated.")
    return report_content
