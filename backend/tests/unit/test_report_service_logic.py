import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
from services.report_service import generate_report_logic
from core.models import ReportLog, ReportStatus

@pytest.mark.asyncio
async def test_generate_report_logic_preserves_extension():
    # Mocks
    mock_db = MagicMock()
    mock_report = MagicMock(spec=ReportLog)
    mock_report.progress_logs = []
    mock_db.query.return_value.filter.return_value.first.return_value = mock_report
    
    file_paths = ["gs://bucket/path/to/document.pdf", "gs://bucket/path/to/image.png"]
    
    with patch("services.report_service.download_file_to_temp") as mock_download, \
         patch("services.report_service.document_processor.process_uploaded_file") as mock_process, \
         patch("services.report_service.llm_handler.generate_report_from_content", new_callable=AsyncMock) as mock_llm, \
         patch("services.report_service.docx_generator.create_styled_docx") as mock_docx, \
         patch("services.report_service.get_storage_client") as mock_gcs, \
         patch("services.report_service.settings") as mock_settings, \
         patch("services.report_service.shutil.rmtree"):
        
        mock_llm.return_value = ("Report Text", 0.01, {})
        mock_process.return_value = {"type": "text", "content": "content"}
        
        # Execute
        await generate_report_logic("report_123", "user_456", file_paths, mock_db)
        
        # Verify download calls
        assert mock_download.call_count == 2
        
        # Check first file call
        args1, _ = mock_download.call_args_list[0]
        gcs_path1, local_path1 = args1
        assert gcs_path1 == "gs://bucket/path/to/document.pdf"
        assert local_path1.endswith(".pdf")
        
        # Check second file call
        args2, _ = mock_download.call_args_list[1]
        gcs_path2, local_path2 = args2
        assert gcs_path2 == "gs://bucket/path/to/image.png"
        assert local_path2.endswith(".png")
        
        # Verify status updates
        assert mock_report.status == ReportStatus.SUCCESS
