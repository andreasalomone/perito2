import logging
from typing import Optional

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash

from core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Basic Auth
auth = HTTPBasicAuth()

# Generate password hash once at startup
# In a real app with multiple users, this would be a database lookup
USERS = {
    settings.AUTH_USERNAME: generate_password_hash(settings.AUTH_PASSWORD)
}

@auth.verify_password
def verify_password(username: str, password: str) -> Optional[str]:
    """
    Verify password for basic auth.
    Returns the username if valid, None otherwise.
    """
    if username in USERS and check_password_hash(USERS.get(username), password):
        logger.debug(f"User '{username}' authenticated successfully.")
        return username
    
    logger.warning(f"Failed authentication attempt for user '{username}'.")
    return None

def get_current_user() -> Optional[str]:
    """Returns the currently authenticated user."""
    return auth.current_user()
