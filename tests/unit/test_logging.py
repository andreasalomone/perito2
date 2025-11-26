import sys
import unittest
from unittest.mock import MagicMock, patch
from core.models import ReportStatus, ExtractionStatus
from services.tasks import generate_report_task
from services.db_service import update_document_log
from core.service_result import ServiceResult, ServiceMessage

class TestLogging(unittest.TestCase):
    def setUp(self):
        self.mock_app_module = MagicMock()
        self.mock_app = self.mock_app_module.app
        self.mock_app.app_context.return_value.__enter__.return_value = None
        self.mock_app.app_context.return_value.__exit__.return_value = None
        
        # Patch sys.modules to mock 'app' module
        self.module_patcher = patch.dict(sys.modules, {'app': self.mock_app_module})
        self.module_patcher.start()

    def tearDown(self):
        self.module_patcher.stop()

    @patch('services.tasks.db_service')
    @patch('services.tasks.file_service')
    @patch('services.tasks.llm_handler')
    def test_generate_report_task_logging_success(self, mock_llm, mock_file_service, mock_db_service):
        # Setup
        report_id = "report-123"
        file_paths = ["/tmp/test.pdf"]
        original_filenames = ["test.pdf"]
        doc_log_ids = ["doc-123"]
        
        # Mock file processing success
        mock_result = ServiceResult(success=True)
        mock_result.data = {
            "processed_entries": [{"type": "text", "content": "Hello World"}],
            "text_length_added": 11
        }
        mock_file_service.process_file_from_path.return_value = mock_result
        
        # Mock LLM response
        mock_llm.generate_report_from_content_sync.return_value = ("Report Content", 0.01, {})

        # Execute
        generate_report_task(report_id, file_paths, original_filenames, doc_log_ids)

        # Verify
        mock_db_service.update_document_log.assert_called_with(
            document_id="doc-123",
            status="success",
            extracted_content_length=11,
            file_type="pdf",
            extraction_method="text"
        )
        
        mock_db_service.update_report_status.assert_any_call(report_id, ReportStatus.PROCESSING)
        mock_db_service.update_report_status.assert_called_with(
            report_id,
            ReportStatus.SUCCESS,
            llm_raw_response="Report Content",
            final_report_text="Report Content",
            api_cost_usd=0.01,
            prompt_token_count=None,
            candidates_token_count=None,
            total_token_count=None,
            cached_content_token_count=None
        )

    @patch('services.tasks.db_service')
    @patch('services.tasks.file_service')
    def test_generate_report_task_logging_failure(self, mock_file_service, mock_db_service):
        # Setup
        report_id = "report-123"
        file_paths = ["/tmp/bad.file"]
        original_filenames = ["bad.file"]
        doc_log_ids = ["doc-456"]
        
        # Mock file processing failure
        mock_result = ServiceResult(success=False)
        mock_result.add_message("Processing failed", "error")
        mock_file_service.process_file_from_path.return_value = mock_result

        # Execute
        generate_report_task(report_id, file_paths, original_filenames, doc_log_ids)

        # Verify
        mock_db_service.update_document_log.assert_called_with(
            document_id="doc-456",
            status="error",
            error_message="Processing failed",
            file_type="file"
        )

    @patch('services.db_service.db')
    def test_update_document_log(self, mock_db):
        # Setup
        mock_doc_log = MagicMock()
        mock_db.session.get.return_value = mock_doc_log
        
        # Execute
        update_document_log(
            document_id="doc-123",
            status="success",
            extracted_content_length=100,
            file_type="pdf"
        )
        
        # Verify
        self.assertEqual(mock_doc_log.extraction_status, ExtractionStatus.SUCCESS)
        self.assertEqual(mock_doc_log.extracted_content_length, 100)
        self.assertEqual(mock_doc_log.file_type, "pdf")
        mock_db.session.commit.assert_called_once()
