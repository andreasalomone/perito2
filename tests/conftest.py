import os
import logging
import pytest
from unittest import mock

# Patch settings before importing app
with mock.patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
    from core.config import settings
    settings.DATABASE_URL = "sqlite:///:memory:"
    from app import app as flask_app

@pytest.fixture
def app():
    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key_for_flashing",
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    
    # Initialize db for tests
    with flask_app.app_context():
        from core.database import db
        # Force engine disposal to ensure new config is picked up
        if db.engine:
            db.engine.dispose()
            
        db.session.remove()
        db.drop_all()
        db.create_all()
        
    # Ensure the logger is configured for tests if it hasn't been already
    if not hasattr(flask_app, "logger_configured_for_tests"):
        logging_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        logging.basicConfig(
            level=logging_level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s",
        )
        flask_app.logger_configured_for_tests = True
    
    yield flask_app
    
    # Cleanup
    with flask_app.app_context():
        from core.database import db
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    client = app.test_client()
    # Set up Basic Auth headers
    import base64
    creds = f"{settings.AUTH_USERNAME}:{settings.AUTH_PASSWORD}"
    b64_creds = base64.b64encode(creds.encode()).decode()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Basic {b64_creds}"
    return client

@pytest.fixture(autouse=True)
def mock_redis():
    with mock.patch("redis.Redis") as mock_redis:
        mock_instance = mock.MagicMock()
        mock_redis.from_url.return_value = mock_instance
        yield mock_instance

