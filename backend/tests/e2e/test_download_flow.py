import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from core.models import ReportLog, ReportStatus
from services.gcs_service import generate_download_signed_url
from deps import get_current_user
from database import get_db

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    mock_db = MagicMock()
    return mock_db

@pytest.fixture
def mock_user_data():
    return {"uid": "test_user_123"}

@pytest.fixture(autouse=True)
def override_dependencies(mock_db_session, mock_user_data):
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: mock_user_data
    yield
    app.dependency_overrides = {}

def test_download_report_success(mock_db_session):
    # Setup mock report
    mock_report = MagicMock(spec=ReportLog)
    mock_report.id = "report_123"
    mock_report.user_id = "test_user_123"
    mock_report.status = ReportStatus.SUCCESS
    mock_report.final_docx_path = "gs://bucket/reports/user_123/report_123/Perizia_Finale.docx"
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_report
    
    # Mock GCS signed URL generation
    with patch("services.gcs_service.get_storage_client") as mock_gcs_client:
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        mock_gcs_client.return_value.bucket.return_value.blob.return_value = mock_blob
        
        # Execute request
        response = client.get("/api/reports/report_123/download")
        
        # Verify
        assert response.status_code == 200
        assert response.json() == {"download_url": "https://storage.googleapis.com/signed-url"}

def test_download_report_not_found(mock_db_session):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    response = client.get("/api/reports/report_123/download")
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"

def test_download_report_unauthorized(mock_db_session):
    mock_report = MagicMock(spec=ReportLog)
    mock_report.id = "report_123"
    mock_report.user_id = "other_user"
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_report
    
    response = client.get("/api/reports/report_123/download")
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"

def test_download_report_not_ready(mock_db_session):
    mock_report = MagicMock(spec=ReportLog)
    mock_report.id = "report_123"
    mock_report.user_id = "test_user_123"
    mock_report.status = ReportStatus.PROCESSING
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_report
    
    response = client.get("/api/reports/report_123/download")
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Report not ready yet"
