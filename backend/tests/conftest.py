import os
import pytest
from unittest import mock

# Set environment variables BEFORE importing anything that uses config
os.environ.update({
    "GOOGLE_CLOUD_PROJECT": "test-project",
    "GOOGLE_CLOUD_REGION": "europe-west1",
    "CLOUD_SQL_CONNECTION_NAME": "project:region:instance",
    "DB_USER": "test_user",
    "DB_PASS": "test_pass",
    "DB_NAME": "test_db",
    "STORAGE_BUCKET_NAME": "test-bucket",
    "CLOUD_TASKS_QUEUE_PATH": "projects/test/locations/test/queues/test",
    "GEMINI_API_KEY": "test-key",
    "RUN_LOCALLY": "true"
})

@pytest.fixture(scope="session", autouse=True)
def mock_env():
    # This fixture is now redundant for import-time config but kept for safety during tests
    yield

