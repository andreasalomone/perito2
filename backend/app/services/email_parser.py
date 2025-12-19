"""
Email parsing utilities using Talon.

Strips quoted text and extracts signatures from email bodies.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy init flag - talon.init() loads ML models (~500ms)
_talon_initialized = False


def _ensure_init() -> bool:
    """Lazily initialize talon. Returns True if successful."""
    global _talon_initialized
    if _talon_initialized:
        return True
    try:
        import talon

        talon.init()
        _talon_initialized = True
        logger.info("✅ Talon email parser initialized")
        return True
    except ImportError:
        logger.warning("Talon not installed (dev environment)")
        return False
    except Exception as e:
        logger.warning(f"Talon init failed: {e}")
        return False


def clean_email_body(
    text: str,
    content_type: str = "text/plain",
    sender_email: Optional[str] = None,
) -> tuple[str, dict]:
    """
    Clean email body: strip quotes, extract signature.

    Args:
        text: Raw email body
        content_type: "text/plain" or "text/html"
        sender_email: Sender address (stored in metadata for future use)

    Returns:
        Tuple of (cleaned_body, metadata_dict)
    """
    metadata: dict = {
        "signature": None,
        "quotes_removed": False,
        "sender": sender_email,
        "original_length": len(text),
    }

    # Fallback if talon not available
    if not _ensure_init():
        return text, metadata

    try:
        from talon import quotations
        from talon.signature.bruteforce import extract_signature

        # Step 1: Strip quoted text
        if content_type == "text/html":
            clean = quotations.extract_from_html(text)
        else:
            clean = quotations.extract_from_plain(text)

        quotes_stripped = len(clean) < len(text)
        metadata["quotes_removed"] = quotes_stripped

        if quotes_stripped:
            logger.debug(f"Stripped {len(text) - len(clean)} chars of quoted text")

        # Step 2: Extract signature (bruteforce - works without sender)
        final_body, sig = extract_signature(clean)
        if sig:
            metadata["signature"] = sig.strip()

        # Fallback: if result is empty, return original
        if not final_body or not final_body.strip():
            logger.warning("Talon returned empty body - using original")
            return text, metadata

        metadata["cleaned_length"] = len(final_body)
        return final_body.strip(), metadata

    except Exception as e:
        logger.warning(f"Talon processing failed: {e} - using original")
        return text, metadata
