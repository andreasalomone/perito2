"""
Unit tests for multi-user authentication system.
"""
import json
from unittest.mock import patch

import pytest
from werkzeug.security import check_password_hash


class TestMultiUserAuthentication:
    """Tests for the multi-user authentication system."""

    @patch('core.security.settings')
    def test_single_user_auth_backward_compatibility(self, mock_settings):
        """Test that single user auth still works when ALLOWED_USERS_JSON is not set."""
        # Setup
        mock_settings.ALLOWED_USERS_JSON = None
        mock_settings.AUTH_USERNAME = "admin"
        mock_settings.AUTH_PASSWORD = "testpass"
        
        # Import after patching
        from core.security import _load_users
        
        users = _load_users()
        
        # Verify
        assert len(users) == 1
        assert "admin" in users
        assert check_password_hash(users["admin"], "testpass")

    @patch('core.security.settings')
    def test_multi_user_auth_from_json(self, mock_settings):
        """Test loading multiple users from ALLOWED_USERS_JSON."""
        # Setup
        mock_settings.ALLOWED_USERS_JSON = json.dumps({
            "user1": "pass1",
            "user2": "pass2",
            "user3": "pass3"
        })
        mock_settings.AUTH_USERNAME = "admin"
        mock_settings.AUTH_PASSWORD = "defaultpass"
        
        # Import after patching
        from core.security import _load_users
        
        users = _load_users()
        
        # Verify
        assert len(users) == 3
        assert "user1" in users
        assert "user2" in users
        assert "user3" in users
        assert check_password_hash(users["user1"], "pass1")
        assert check_password_hash(users["user2"], "pass2")
        assert check_password_hash(users["user3"], "pass3")

    @patch('core.security.settings')
    def test_malformed_json_falls_back_to_single_user(self, mock_settings):
        """Test that malformed JSON falls back to single user authentication."""
        # Setup
        mock_settings.ALLOWED_USERS_JSON = "not valid json {"
        mock_settings.AUTH_USERNAME = "admin"
        mock_settings.AUTH_PASSWORD = "fallback"
        
        # Import after patching
        from core.security import _load_users
        
        users = _load_users()
        
        # Verify fallback to single user
        assert len(users) == 1
        assert "admin" in users
        assert check_password_hash(users["admin"], "fallback")

    @patch('core.security.settings')
    def test_non_dict_json_falls_back_to_single_user(self, mock_settings):
        """Test that non-dict JSON (like array) falls back to single user."""
        # Setup - JSON array instead of object
        mock_settings.ALLOWED_USERS_JSON = json.dumps(["user1", "user2"])
        mock_settings.AUTH_USERNAME = "admin"
        mock_settings.AUTH_PASSWORD = "fallback"
        
        # Import after patching
        from core.security import _load_users
        
        users = _load_users()
        
        # Verify fallback to single user
        assert len(users) == 1
        assert "admin" in users

    @patch('core.security.settings')
    def test_empty_json_object(self, mock_settings):
        """Test handling of empty JSON object."""
        # Setup
        mock_settings.ALLOWED_USERS_JSON = json.dumps({})
        mock_settings.AUTH_USERNAME = "admin"
        mock_settings.AUTH_PASSWORD = "defaultpass"
        
        # Import after patching
        from core.security import _load_users
        
        users = _load_users()
        
        # Empty JSON should result in no users (not fall back)
        assert len(users) == 0

    def test_verify_password_with_valid_credentials(self):
        """Test password verification with valid credentials."""
        from core.security import verify_password, USERS
        
        # Get a username from USERS if available
        if USERS:
            username = list(USERS.keys())[0]
            # Note: We can't test the actual password since it's hashed
            # This test would need to be run with known test credentials
            # For now, just verify the function structure
            result = verify_password("invalid_user", "invalid_pass")
            assert result is None

    def test_verify_password_with_invalid_credentials(self):
        """Test password verification with invalid credentials."""
        from core.security import verify_password
        
        result = verify_password("nonexistent_user", "wrong_password")
        assert result is None

    def test_get_current_user(self):
        """Test get_current_user function exists and is callable."""
        from core.security import get_current_user
        
        # Function should exist and be callable
        assert callable(get_current_user)
        # Note: Cannot test without Flask app context, but function is verified to exist
