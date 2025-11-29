"""
Unit tests for prompt builder service.
"""

from unittest.mock import MagicMock
from services.llm import prompt_builder_service

def test_build_prompt_parts_includes_ocr_instruction():
    """Test that the final prompt includes the OCR instruction."""
    # Arrange
    processed_files = []
    additional_text = ""
    uploaded_file_objects = []
    upload_error_messages = []
    use_cache = False

    # Act
    prompt_parts = prompt_builder_service.build_prompt_parts(
        processed_files,
        additional_text,
        uploaded_file_objects,
        upload_error_messages,
        use_cache
    )

    # Assert
    # The last part should be the final instruction string
    final_instruction = prompt_parts[-1]
    assert isinstance(final_instruction, str)
    assert "Per i documenti scansionati o le immagini, esegui l'OCR" in final_instruction
