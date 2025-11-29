"""Prompt builder service for assembling LLM prompts."""

import logging
from typing import Any, Dict, List, Union

from google.genai import types

from core.prompt_config import (
    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI,
    SCHEMA_REPORT,
    SYSTEM_INSTRUCTION,
)

logger = logging.getLogger(__name__)


def build_text_file_parts(processed_files: List[Dict[str, Any]]) -> List[str]:
    """Builds text parts from processed files.

    Args:
        processed_files: List of processed file information dictionaries.

    Returns:
        List of text strings to include in the prompt.
    """
    processed_text_files_parts: List[str] = []

    for file_info in processed_files:
        if file_info.get("type") == "text":
            filename = file_info.get("filename", "documento testuale")
            content = file_info.get("content", "")
            if content:
                processed_text_files_parts.append(
                    f"--- INIZIO CONTENUTO DA FILE: {filename} ---\n"
                )
                processed_text_files_parts.append(content)
                processed_text_files_parts.append(
                    f"\n--- FINE CONTENUTO DA FILE: {filename} ---\n\n"
                )
        elif file_info.get("type") == "error":
            filename = file_info.get("filename", "file sconosciuto")
            message = file_info.get("message", "errore generico")
            processed_text_files_parts.append(
                f"\n\n[AVVISO: Problema durante l'elaborazione del file {filename}: {message}]\n\n"
            )
        elif file_info.get("type") == "unsupported":
            filename = file_info.get("filename", "file sconosciuto")
            message = file_info.get("message", "tipo non supportato")
            processed_text_files_parts.append(
                f"\n\n[AVVISO: Il file {filename} è di un tipo non supportato e non può essere processato: {message}]\n\n"
            )

    return processed_text_files_parts


def truncate_content(text_parts: List[str], max_chars: int = 3500000) -> List[str]:
    """Truncates the list of text parts to fit within the character limit.

    Args:
        text_parts: List of text strings.
        max_chars: Maximum total characters allowed (default ~3.5M chars ≈ 875k tokens).

    Returns:
        Truncated list of text strings.
    """
    total_chars = sum(len(part) for part in text_parts)

    if total_chars <= max_chars:
        return text_parts

    logger.warning(
        f"Total text content length ({total_chars}) exceeds limit ({max_chars}). Truncating."
    )

    current_chars = 0
    truncated_parts = []

    for part in text_parts:
        if current_chars >= max_chars:
            break

        remaining_chars = max_chars - current_chars
        if len(part) <= remaining_chars:
            truncated_parts.append(part)
            current_chars += len(part)
        else:
            # Truncate this part and stop
            truncated_parts.append(
                part[:remaining_chars] + "\n... [TRUNCATED DUE TO LENGTH LIMIT] ..."
            )
            current_chars += remaining_chars
            break

    return truncated_parts


# Expose system prompts for fallback logic
SYSTEM_PROMPTS = [
    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI,
    "\n\n",
    SCHEMA_REPORT,
    "\n\n",
    SYSTEM_INSTRUCTION,
    "\n\n",
]


def build_prompt_parts(
    processed_files: List[Dict[str, Any]],
    additional_text: str,
    uploaded_file_objects: List[types.File],
    upload_error_messages: List[str],
    use_cache: bool,
) -> List[Union[str, types.Part, types.File]]:
    """Builds complete prompt parts for LLM generation.

    Args:
        processed_files: List of processed file information dictionaries.
        additional_text: Additional text to include in the prompt.
        uploaded_file_objects: List of uploaded File objects for vision files.
        upload_error_messages: List of error messages for failed uploads.
        use_cache: Whether to use cached prompts or include them directly.

    Returns:
        List of prompt parts (strings, Parts, or Files) for the LLM.
    """
    final_prompt_parts: List[Union[str, types.Part, types.File]] = []

    # Add fallback prompts if not using cache
    if not use_cache:
        logger.info("Including prompts directly (not using cache).")
        final_prompt_parts.extend(SYSTEM_PROMPTS)

    # Add text file parts
    text_parts = build_text_file_parts(processed_files)

    # Truncate text parts if necessary to avoid token limits
    text_parts = truncate_content(text_parts)

    final_prompt_parts.extend(text_parts)

    # Add upload error messages
    final_prompt_parts.extend(upload_error_messages)

    # Add additional text if provided
    if additional_text.strip():
        final_prompt_parts.append(
            f"--- INIZIO TESTO AGGIUNTIVO FORNITO ---\n{additional_text}\n--- FINE TESTO AGGIUNTIVO FORNITO ---\n"
        )

    # Add uploaded file objects (references) to the prompt parts
    final_prompt_parts.extend(uploaded_file_objects)

    # Add final instruction
    final_instruction = "\n\nAnalizza TUTTI i documenti, foto e testi forniti (sia quelli caricati come file referenziati, sia quelli inclusi direttamente come testo) e genera il report. Per i documenti scansionati o le immagini, esegui l'OCR per estrarre tutto il testo visibile."
    if use_cache:
        final_instruction += " Utilizza le istruzioni di stile, struttura e sistema precedentemente cachate."
    else:
        final_instruction += " Utilizza le istruzioni di stile, struttura e sistema fornite all'inizio di questo prompt."
    final_prompt_parts.append(final_instruction)

    return final_prompt_parts
