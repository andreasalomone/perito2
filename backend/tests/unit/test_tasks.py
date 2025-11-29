import pytest
from unittest.mock import MagicMock, patch
from services.tasks import generate_report_task
from core.models import ReportStatus
from core.service_result import ServiceResult

@pytest.fixture
def mock_app():
    with patch("app.app") as mock:
        mock.app_context.return_value.__enter__.return_value = None
        yield mock

@patch("services.tasks.db_service")
@patch("services.tasks.file_service")
@patch("services.tasks.llm_handler")
def test_generate_report_task_multimodal(mock_llm_handler, mock_file_service, mock_db_service, mock_app):
    # Setup
    report_id = 123
    file_paths = ["/tmp/test.pdf"]
    original_filenames = ["test.pdf"]
    document_log_ids = ["doc_1"]

    # Mock file processing result
    mock_result = ServiceResult(success=True)
    mock_result.data = {
        "processed_entries": [
            {
                "type": "vision",
                "path": "/tmp/test.pdf",
                "mime_type": "application/pdf",
                "filename": "test.pdf"
            },
            {
                "type": "text",
                "content": "Extracted text content",
                "filename": "test.pdf (extracted text)"
            }
        ],
        "text_length_added": 100
    }
    mock_file_service.process_file_from_path.return_value = mock_result

    # Mock LLM response
    mock_llm_handler.generate_report_from_content_sync.return_value = ("Generated Report", 0.05, {})

    # Execute
    generate_report_task(
        report_id=report_id,
        file_paths=file_paths,
        original_filenames=original_filenames,
        document_log_ids=document_log_ids
    )

    # Verify
    # 1. Verify file service was called
    mock_file_service.process_file_from_path.assert_called_once()

    # 2. Verify LLM handler was called with BOTH vision and text parts
    mock_llm_handler.generate_report_from_content_sync.assert_called_once()
    call_args = mock_llm_handler.generate_report_from_content_sync.call_args
    processed_files_arg = call_args.kwargs.get("processed_files")
    
    assert len(processed_files_arg) == 2
    assert processed_files_arg[0]["type"] == "vision"
    assert processed_files_arg[1]["type"] == "text"
    assert processed_files_arg[1]["content"] == "Extracted text content"

    # 3. Verify DB updates
    mock_db_service.update_report_status.assert_any_call(report_id, ReportStatus.PROCESSING)
    mock_db_service.update_report_status.assert_any_call(
        report_id, 
        ReportStatus.SUCCESS, 
        llm_raw_response="Generated Report",
        final_report_text="Generated Report",
        api_cost_usd=0.05,
        prompt_token_count=None,
        candidates_token_count=None,
        total_token_count=None,
        cached_content_token_count=None
    )
