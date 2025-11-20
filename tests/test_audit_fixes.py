import pytest
from unittest.mock import MagicMock, patch
import os

# Patch settings and auth before importing app
mock_auth = MagicMock()
mock_auth.login_required = lambda f: f

with patch('core.config.settings.REDIS_URL', "memory://"), \
     patch('core.security.auth', mock_auth):
    from app import app
from services import db_service


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False # Disable rate limiting for tests
    with app.test_client() as client:
        yield client

import io

@patch('services.db_service.get_report_log')
@patch('services.docx_generator.create_styled_docx')
def test_download_report_success(mock_create_docx, mock_get_report_log, client):
    # Mock report log
    mock_report = MagicMock()
    mock_report.final_report_text = "Test Report Content"
    mock_report.llm_raw_response = "Test Report Content"
    mock_get_report_log.return_value = mock_report
    
    # Mock docx generation to return a real BytesIO object
    mock_create_docx.return_value = io.BytesIO(b"fake docx content")

    # Mock authentication (bypass login_required)
    with client.session_transaction() as sess:
        sess['_user_id'] = '1' # Simulate logged in user if using Flask-Login or similar

    headers = {
        'Authorization': 'Basic YWRtaW46ZGVmYXVsdHBhc3N3b3Jk' # admin:defaultpassword base64
    }

    response = client.post('/download_report/test_report_id', headers=headers)
    
    if response.status_code == 302:
        # Follow redirect to see flash messages
        response = client.get(response.location)
        print(response.data.decode())

    assert response.status_code == 200
    assert response.headers['Content-Disposition'].startswith('attachment; filename=Perizia_')
    mock_get_report_log.assert_called_with('test_report_id')

@patch('services.db_service.get_report_log')
def test_download_report_not_found(mock_get_report_log, client):
    mock_get_report_log.return_value = None
    
    headers = {
        'Authorization': 'Basic YWRtaW46ZGVmYXVsdHBhc3N3b3Jk'
    }

    response = client.post('/download_report/invalid_id', headers=headers)
    
    # Should redirect to index with flash message
    assert response.status_code == 302
    assert response.location == '/'
