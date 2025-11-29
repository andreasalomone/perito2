import pytest
from unittest.mock import MagicMock, patch
from core.models import ReportLog, ReportStatus
from services import db_service, tasks
import json

@pytest.fixture
def mock_app():
    from app import app
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app

@pytest.fixture
def mock_db_session():
    with patch('services.db_service.db.session') as mock_session:
        yield mock_session

def test_append_report_log(mock_db_session):
    # Setup
    mock_report = MagicMock(spec=ReportLog)
    mock_report.progress_logs = []
    mock_report.current_step = "queued"
    mock_db_session.get.return_value = mock_report

    # Execute
    db_service.append_report_log("test-id", "Test message", "processing")

    # Verify
    assert len(mock_report.progress_logs) == 1
    assert mock_report.progress_logs[0]["message"] == "Test message"
    assert "timestamp" in mock_report.progress_logs[0]
    assert mock_report.current_step == "processing"
    mock_db_session.commit.assert_called_once()

@patch('services.tasks.file_service')
@patch('services.tasks.llm_handler')
@patch('services.tasks.db_service')
def test_generate_report_task_emits_logs(mock_db_service, mock_llm_handler, mock_file_service, mock_app):
    # Setup
    mock_file_service.process_file_from_path.return_value.success = True
    mock_file_service.process_file_from_path.return_value.data = {
        "processed_entries": [{"type": "text", "content": "test content"}],
        "text_length_added": 12
    }
    
    mock_llm_handler.generate_report_from_content_sync.return_value = (
        "Generated Report", 0.01, {}
    )

    # Execute
    with mock_app.app_context():
        tasks.generate_report_task(
            report_id="test-id",
            file_paths=["/tmp/test.pdf"],
            original_filenames=["test.pdf"],
            document_log_ids=["doc-id"]
        )

    # Verify calls to append_report_log
    # We expect at least: start, file processing, text extracted, generation start, completion
    assert mock_db_service.append_report_log.call_count >= 5
    
    # Check specific log messages were attempted
    calls = mock_db_service.append_report_log.call_args_list
    messages = [call[0][1] for call in calls]
    
    assert "Inizio elaborazione..." in messages
    assert any("Analisi file: test.pdf" in m for m in messages)
    assert any("Testo estratto da test.pdf" in m for m in messages)
    assert "Generazione report con AI in corso..." in messages
    assert "Report generato con successo." in messages
