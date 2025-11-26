import io
import pytest
from unittest import mock

def test_upload_invalid_extension(client, tmp_path):
    """Verify upload fails with invalid extension."""
    # Patch UPLOAD_FOLDER to use a temporary directory
    with mock.patch('core.config.settings.UPLOAD_FOLDER', str(tmp_path)):
        data = {
            'files': (io.BytesIO(b"exe content"), 'malicious.exe')
        }
        response = client.post('/upload', data=data, content_type='multipart/form-data')
    
    # Depending on implementation, this might be 400 or 200 with error message
    # Based on app.py: return jsonify({"error": "Upload failed", ...}), 400
    assert response.status_code == 400
    assert b"Upload failed" in response.data

def test_upload_too_large(client, tmp_path):
    """Verify upload fails if file is too large."""
    # Patch MAX_FILE_SIZE_BYTES to be very small (e.g., 10 bytes)
    # We also need to patch UPLOAD_FOLDER to avoid FS errors if it tries to save
    with mock.patch('core.config.settings.MAX_FILE_SIZE_MB', 0.00001): # ~10 bytes
        with mock.patch('core.config.settings.UPLOAD_FOLDER', str(tmp_path)):
            data = {
                'files': (io.BytesIO(b"This is a very long file content that should exceed the limit"), 'large.txt')
            }
            response = client.post('/upload', data=data, content_type='multipart/form-data')
            
            # Should be skipped or error. 
            # app.py logic: if file_size > limit: result.add_message(..., "warning") and continue
            # If all files skipped, result.success = False -> 400
            assert response.status_code == 400
            assert b"exceeds size limit" in response.data or b"No valid files were saved" in response.data
