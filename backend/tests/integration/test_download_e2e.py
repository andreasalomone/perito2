import io
import zipfile
import pytest
from unittest import mock
from core.models import ReportLog, ReportStatus

def test_download_report_e2e_content_verification(client, app):
    """
    E2E-style integration test.
    1. Mocks the DB to return a report.
    2. Calls the download endpoint with different formats.
    3. ACTUALLY runs the generators (no mocking of generators).
    4. Inspects the generated DOCX file (unzipping it) to verify the footer text.
    """
    report_id = "e2e_test_report_id"
    
    # Mock database service to return a valid report log
    with mock.patch("services.db_service.get_report_log") as mock_get_report:
        mock_report = mock.MagicMock(spec=ReportLog)
        mock_report.id = report_id
        mock_report.status = ReportStatus.SUCCESS
        mock_report.final_report_text = "E2E Test Report Content"
        mock_report.llm_raw_response = "E2E Test Report Content"
        mock_get_report.return_value = mock_report

        # --- Test Case 1: BN Surveys (Default) ---
        response = client.get(f"/download_report/{report_id}?format=bn_surveys")
        assert response.status_code == 200
        
        # Open the response content as a ZipFile (DOCX is a zip)
        docx_stream = io.BytesIO(response.data)
        with zipfile.ZipFile(docx_stream) as z:
            # Search for footer text in all xml files (usually word/footer1.xml)
            found_bn_text = False
            for filename in z.namelist():
                if filename.startswith("word/footer") and filename.endswith(".xml"):
                    xml_content = z.read(filename).decode("utf-8")
                    if "BN Surveys Srls" in xml_content:
                        found_bn_text = True
                        break
            
            assert found_bn_text, "Could not find 'BN Surveys Srls' in the generated DOCX footer (BN Surveys format)."

        # --- Test Case 2: Salomone & Associati ---
        response = client.get(f"/download_report/{report_id}?format=salomone")
        assert response.status_code == 200
        
        # Open the response content as a ZipFile
        docx_stream = io.BytesIO(response.data)
        with zipfile.ZipFile(docx_stream) as z:
            # Search for footer text
            found_salomone_text = False
            for filename in z.namelist():
                if filename.startswith("word/footer") and filename.endswith(".xml"):
                    xml_content = z.read(filename).decode("utf-8")
                    # Check for "Salomone" which is unique enough and avoids XML escaping issues with "&"
                    if "Salomone" in xml_content and "ASSOCIATI" in xml_content:
                        found_salomone_text = True
                        break
            
            assert found_salomone_text, f"Could not find 'Salomone' and 'ASSOCIATI' in the generated DOCX footer (Salomone format). Content of last footer: {xml_content if 'xml_content' in locals() else 'N/A'}"
