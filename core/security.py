import json
import logging
from typing import Dict, Optional

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash

from core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Basic Auth
auth = HTTPBasicAuth()


def _load_users() -> Dict[str, str]:
    """
    Load user credentials from configuration.

    Returns:
        Dict mapping usernames to password hashes
    """
    users = {}

    # Try to load from ALLOWED_USERS_JSON first
    if settings.ALLOWED_USERS_JSON:
        try:
            users_config = json.loads(settings.ALLOWED_USERS_JSON)
            if not isinstance(users_config, dict):
                logger.error("ALLOWED_USERS_JSON must be a JSON object (dict)")
                # Fall back to single user
                users[settings.AUTH_USERNAME] = generate_password_hash(
                    settings.AUTH_PASSWORD
                )
            else:
                for username, password in users_config.items():
                    users[username] = generate_password_hash(password)
                logger.info(f"Loaded {len(users)} user(s) from ALLOWED_USERS_JSON")
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse ALLOWED_USERS_JSON: {e}. Falling back to single user auth."
            )
            # Fall back to single user
            users[settings.AUTH_USERNAME] = generate_password_hash(
                settings.AUTH_PASSWORD
            )
    else:
        # Use single user authentication (backward compatibility)
        users[settings.AUTH_USERNAME] = generate_password_hash(settings.AUTH_PASSWORD)
        logger.info(f"Using single user authentication for '{settings.AUTH_USERNAME}'")

    return users


# Load users at startup
USERS = _load_users()


@auth.verify_password
def verify_password(username: str, password: str) -> Optional[str]:
    """
    Verify password for basic auth.
    Returns the username if valid, None otherwise.
    """
    if username in USERS and check_password_hash(USERS.get(username), password):
        logger.info(f"User '{username}' authenticated successfully.")
        return username

    logger.warning(f"Failed authentication attempt for user '{username}'.")
    return None


def get_current_user() -> Optional[str]:
    """Returns the currently authenticated user."""
    return auth.current_user()
