import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime

# Adjust import path as needed based on where this file sits relative to app root
# Assuming running from 'backend/' root or similar, and 'main' is available.
# If 'main' is not easily importable, we might need to construct the app or router.
# For this example, we'll assume we can import the router and create a simple app for testing.

from fastapi import FastAPI
from routes import cases
from deps import get_db, get_current_user_token
from schemas import CaseRead, CaseCreate, CaseStatus

# Setup Test App
app = FastAPI()
app.include_router(cases.router, prefix="/cases")

client = TestClient(app)

# --- Fixtures ---

@pytest.fixture
def mock_db_session():
    """Mocks the SQLAlchemy Session."""
    return MagicMock()

@pytest.fixture
def mock_user_token():
    """Mocks the current user token dependency."""
    return {"organization_id": uuid4(), "sub": "test_user"}

@pytest.fixture
def override_deps(mock_db_session, mock_user_token):
    """Overrides FastAPI dependencies."""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_current_user_token] = lambda: mock_user_token
    yield
    app.dependency_overrides = {}

# --- Tests ---

def test_list_cases_happy_path(override_deps, mock_db_session):
    # Arrange
    mock_case = MagicMock()
    mock_case.id = uuid4()
    mock_case.reference_code = "REF-001"
    mock_case.status = CaseStatus.OPEN
    mock_case.created_at = datetime.now()
    
    mock_db_session.query.return_value.order_by.return_value.all.return_value = [mock_case]

    # Act
    response = client.get("/cases/")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["reference_code"] == "REF-001"

def test_create_case_happy_path(override_deps, mock_db_session, mock_user_token):
    # Arrange
    payload = {
        "reference_code": "NEW-CASE-001",
        "client_name": "Test Client"
    }
    
    # Mock the Client lookup/creation service call if it exists, 
    # but here we just need to ensure db.add/commit are called.
    # We might need to mock 'case_service.get_or_create_client' if it's called.
    with patch("services.case_service.get_or_create_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.id = uuid4()
        mock_get_client.return_value = mock_client
        
        # Act
        response = client.post("/cases/", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["reference_code"] == "NEW-CASE-001"
    assert data["status"] == "open"
    
    # Verify DB interactions
    mock_db_session.add.assert_called()
    mock_db_session.commit.assert_called()
    mock_db_session.refresh.assert_called()

def test_get_case_happy_path(override_deps, mock_db_session):
    # Arrange
    case_id = uuid4()
    mock_case = MagicMock()
    mock_case.id = case_id
    mock_case.reference_code = "EXISTING-001"
    mock_case.documents = []
    mock_case.report_versions = []
    
    # Mock query chain: query(Case).filter(...).first()
    mock_query = mock_db_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.return_value = mock_case

    # Act
    response = client.get(f"/cases/{case_id}")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(case_id)
    assert data["reference_code"] == "EXISTING-001"

def test_get_case_not_found(override_deps, mock_db_session):
    # Arrange
    case_id = uuid4()
    # Mock return None
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Act
    response = client.get(f"/cases/{case_id}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Case not found"

def test_upload_url_happy_path(override_deps, mock_db_session):
    # Arrange
    case_id = uuid4()
    mock_case = MagicMock()
    mock_case.id = case_id
    mock_case.organization_id = uuid4()
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_case
    
    # Mock GCS service
    with patch("services.gcs_service.generate_upload_signed_url") as mock_gcs:
        mock_gcs.return_value = {
            "upload_url": "https://fake-gcs/upload",
            "gcs_path": "uploads/file.pdf"
        }
        
        # Act
        response = client.post(f"/cases/{case_id}/documents/upload-url", params={
            "filename": "test.pdf",
            "content_type": "application/pdf"
        })

    # Assert
    assert response.status_code == 200
    assert response.json()["upload_url"] == "https://fake-gcs/upload"

def test_register_document_happy_path(override_deps, mock_db_session):
    # Arrange
    case_id = uuid4()
    mock_case = MagicMock()
    mock_case.id = case_id
    mock_case.organization_id = uuid4()
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_case
    
    payload = {
        "gcs_path": "uploads/test.pdf",
        "filename": "test.pdf"
    }
    
    # Mock trigger task
    with patch("services.case_service.trigger_extraction_task") as mock_trigger:
        # Act
        response = client.post(f"/cases/{case_id}/documents/register", params=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["ai_status"] == "pending"
        
        mock_trigger.assert_called_once()
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()
