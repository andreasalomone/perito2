import pytest
from unittest import mock
import os
import sys

# Ensure backend is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Set dummy env vars for Settings
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test")
os.environ.setdefault("CLOUD_SQL_CONNECTION_NAME", "test")
os.environ.setdefault("DB_PASS", "test")
os.environ.setdefault("STORAGE_BUCKET_NAME", "test")
os.environ.setdefault("CLOUD_TASKS_QUEUE_PATH", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")

from services.file_service import process_file_from_path
from core.service_result import ServiceResult

@mock.patch("services.file_service.document_processor")
@mock.patch("services.file_service.settings")
def test_process_file_from_path_success(mock_settings, mock_processor):
    # Setup mocks
    mock_settings.MAX_EXTRACTED_TEXT_LENGTH = 1000
    
    # Mock document_processor returning a list (new simplified logic)
    mock_processor.process_uploaded_file.return_value = [
        {
            "type": "text",
            "filename": "test.txt",
            "content": "Hello World",
            "source": "test"
        },
        {
            "type": "vision",
            "filename": "image.png",
            "mime_type": "image/png"
        }
    ]
    
    # Call function
    result = process_file_from_path("/tmp/test.txt", "test.txt", 0)
    
    # Assertions
    assert result.success is True
    assert len(result.data["processed_entries"]) == 2
    assert result.data["processed_entries"][0]["content"] == "Hello World"
    assert result.data["processed_entries"][1]["type"] == "vision"
    assert result.data["text_length_added"] == 11

@mock.patch("services.file_service.document_processor")
@mock.patch("services.file_service.settings")
def test_process_file_from_path_truncation(mock_settings, mock_processor):
    # Setup mocks
    mock_settings.MAX_EXTRACTED_TEXT_LENGTH = 5
    
    mock_processor.process_uploaded_file.return_value = [
        {
            "type": "text",
            "filename": "test.txt",
            "content": "Hello World", # 11 chars, limit is 5
            "source": "test"
        }
    ]
    
    # Call function
    result = process_file_from_path("/tmp/test.txt", "test.txt", 0)
    
    # Assertions
    assert result.success is True
    assert len(result.data["processed_entries"]) == 1
    assert result.data["processed_entries"][0]["content"] == "Hello" # Truncated
    assert result.data["text_length_added"] == 5
    assert len(result.messages) > 0
    assert "truncated" in result.messages[0].message

@mock.patch("services.file_service.document_processor")
@mock.patch("services.file_service.settings")
def test_process_file_from_path_error(mock_settings, mock_processor):
    # Setup mocks
    mock_processor.process_uploaded_file.side_effect = Exception("Processing failed")
    
    # Call function
    result = process_file_from_path("/tmp/test.txt", "test.txt", 0)
    
    # Assertions
    assert result.success is True # It returns success=True but with error entry
    assert len(result.data["processed_entries"]) == 1
    assert result.data["processed_entries"][0]["type"] == "error"
    assert "Processing failed" in str(result.data["processed_entries"][0]["message"]) or "unexpected error" in str(result.data["processed_entries"][0]["message"])
