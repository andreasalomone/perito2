import os
import logging
import pytest
from unittest import mock

# Patch settings before importing app
with mock.patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
    from core.config import settings
    settings.DATABASE_URL = "sqlite:///:memory:"
    settings.REDIS_URL = "memory://"
    from app import app as flask_app
    from app import limiter

@pytest.fixture
def app():
    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key_for_flashing",
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": False,
        }
    )
    
    limiter.enabled = False
    
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
    from werkzeug.security import generate_password_hash
    
    # Define test credentials
    test_username = "testuser"
    test_password = "testpassword"
    
    # Patch the USERS dict in core.security to ensure we have a known valid user
    # We use mock.patch.dict to update the global USERS dictionary in core.security
    with mock.patch.dict("core.security.USERS", {test_username: generate_password_hash(test_password)}, clear=True):
        client = app.test_client()
        
        # Set up Basic Auth headers
        import base64
        creds = f"{test_username}:{test_password}"
        b64_creds = base64.b64encode(creds.encode()).decode()
        client.environ_base["HTTP_AUTHORIZATION"] = f"Basic {b64_creds}"
        
        yield client

@pytest.fixture(autouse=True)
def mock_redis():
    with mock.patch("redis.Redis") as mock_redis:
        mock_instance = mock.MagicMock()
        mock_redis.from_url.return_value = mock_instance
        yield mock_instance

