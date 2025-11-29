import io
import pytest
from unittest import mock
from core.models import ReportLog, ReportStatus

def test_download_report_format_selection(client, app):
    """
    Test that the download_report endpoint selects the correct generator
    based on the 'format' query parameter.
    """
    report_id = "test_report_id"
    
    # Mock database service to return a valid report log
    with mock.patch("services.db_service.get_report_log") as mock_get_report:
        mock_report = mock.MagicMock(spec=ReportLog)
        mock_report.id = report_id
        mock_report.status = ReportStatus.SUCCESS
        mock_report.final_report_text = "Test report content"
        mock_report.llm_raw_response = "Test report content"
        mock_get_report.return_value = mock_report

        # Mock both generators
        with mock.patch("services.docx_generator.create_styled_docx") as mock_bn_gen, \
             mock.patch("services.docx_generator_salomone.create_styled_docx") as mock_salomone_gen:
            
            # Setup mocks to return a dummy stream
            mock_bn_gen.return_value = io.BytesIO(b"BN Content")
            mock_salomone_gen.return_value = io.BytesIO(b"Salomone Content")

            # Case 1: Default (no format specified) -> Should use BN Surveys
            response = client.get(f"/download_report/{report_id}")
            assert response.status_code == 200
            mock_bn_gen.assert_called()
            mock_salomone_gen.assert_not_called()
            
            # Reset mocks
            mock_bn_gen.reset_mock()
            mock_salomone_gen.reset_mock()

            # Case 2: Explicit 'bn_surveys' -> Should use BN Surveys
            response = client.get(f"/download_report/{report_id}?format=bn_surveys")
            assert response.status_code == 200
            mock_bn_gen.assert_called()
            mock_salomone_gen.assert_not_called()

            # Reset mocks
            mock_bn_gen.reset_mock()
            mock_salomone_gen.reset_mock()

            # Case 3: Explicit 'salomone' -> Should use Salomone & Associati
            response = client.get(f"/download_report/{report_id}?format=salomone")
            assert response.status_code == 200
            mock_salomone_gen.assert_called()
            mock_bn_gen.assert_not_called()
