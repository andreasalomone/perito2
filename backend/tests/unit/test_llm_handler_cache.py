import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, mock_open, patch

# Temporarily adjust sys.path to import from the parent directory (project root)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from google.api_core import exceptions as google_exceptions
from google.genai import (
    types as genai_types,
)

from core.config import settings
from core.prompt_config import (
    PREDEFINED_STYLE_REFERENCE_TEXT,
    REPORT_STRUCTURE_PROMPT,
    SYSTEM_INSTRUCTION,
)

# The module and function to test
from services.llm.cache_service import get_or_create_prompt_cache


class TestGetOrCreatePromptCache(unittest.TestCase):

    def setUp(self):
        """Set up for each test method."""
        # Store original settings
        self.original_cache_name = settings.REPORT_PROMPT_CACHE_NAME
        self.original_model_name = settings.LLM_MODEL_NAME
        self.original_cache_ttl_days = settings.CACHE_TTL_DAYS
        self.original_cache_display_name = settings.CACHE_DISPLAY_NAME
        self.original_retry_attempts = settings.LLM_API_RETRY_ATTEMPTS
        self.original_retry_wait = settings.LLM_API_RETRY_WAIT_SECONDS
        self.original_cache_state_file = settings.CACHE_STATE_FILE

        # Set default test values
        settings.LLM_MODEL_NAME = "gemini-test-model"
        settings.CACHE_TTL_DAYS = 1
        settings.CACHE_DISPLAY_NAME = "TestCacheDisplayName"
        settings.REPORT_PROMPT_CACHE_NAME = None
        settings.LLM_API_RETRY_ATTEMPTS = 1
        settings.LLM_API_RETRY_WAIT_SECONDS = 0
        settings.CACHE_STATE_FILE = "test_cache_state.json"

    def tearDown(self):
        """Clean up after each test method."""
        settings.REPORT_PROMPT_CACHE_NAME = self.original_cache_name
        settings.LLM_MODEL_NAME = self.original_model_name
        settings.CACHE_TTL_DAYS = self.original_cache_ttl_days
        settings.CACHE_DISPLAY_NAME = self.original_cache_display_name
        settings.LLM_API_RETRY_ATTEMPTS = self.original_retry_attempts
        settings.LLM_API_RETRY_WAIT_SECONDS = self.original_retry_wait
        settings.CACHE_STATE_FILE = self.original_cache_state_file

    @patch("services.llm.cache_service.os.path.exists")
    @patch("services.llm.cache_service.open", new_callable=mock_open)
    @patch("services.llm.cache_service.json.load")
    @patch("services.llm.cache_service.genai.Client")
    def test_create_cache_success_no_existing_name(
        self, MockGenaiClient, mock_json_load, mock_file_open, mock_path_exists
    ):
        """Test successful cache creation when no cache name exists anywhere."""
        # Setup mocks
        mock_path_exists.return_value = False  # No state file
        settings.REPORT_PROMPT_CACHE_NAME = None

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/newlyCreatedCache123"
        mock_cache_create_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        # Execute
        result_cache_name = get_or_create_prompt_cache(mock_client_instance)

        # Assertions
        self.assertEqual(result_cache_name, "cachedContents/newlyCreatedCache123")
        mock_client_instance.caches.create.assert_called_once()
        
        # Verify file write (saving the new cache name)
        mock_file_open.assert_called_with(os.path.abspath(settings.CACHE_STATE_FILE), "w")
        handle = mock_file_open()
        # Check that json.dump was called (or write was called with json string)
        # Since we didn't mock json.dump, we can check the write calls if we want, 
        # but better to mock json.dump to verify what's being dumped.
        # However, in the code we use json.dump(obj, f).
        # Let's mock json.dump in the decorator list.
        
    @patch("services.llm.cache_service.json.dump")
    @patch("services.llm.cache_service.os.makedirs")
    @patch("services.llm.cache_service.os.path.exists")
    @patch("services.llm.cache_service.open", new_callable=mock_open)
    @patch("services.llm.cache_service.genai.Client")
    def test_create_cache_and_save_state(
        self, MockGenaiClient, mock_file_open, mock_path_exists, mock_makedirs, mock_json_dump
    ):
        """Test that a new cache is created and its name is saved to the state file."""
        mock_path_exists.return_value = False
        settings.REPORT_PROMPT_CACHE_NAME = None

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/newCacheXYZ"
        mock_cache_create_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        get_or_create_prompt_cache(mock_client_instance)

        # Verify save logic
        mock_makedirs.assert_called_once()
        mock_file_open.assert_called_with(os.path.abspath(settings.CACHE_STATE_FILE), "w")
        mock_json_dump.assert_called_once()
        args, _ = mock_json_dump.call_args
        self.assertEqual(args[0]["cache_name"], "newCacheXYZ")

    @patch("services.llm.cache_service.os.path.exists")
    @patch("services.llm.cache_service.open", new_callable=mock_open)
    @patch("services.llm.cache_service.json.load")
    @patch("services.llm.cache_service.genai.Client")
    def test_retrieve_cache_from_state_file(
        self, MockGenaiClient, mock_json_load, mock_file_open, mock_path_exists
    ):
        """Test retrieving a cache name from the state file."""
        # Setup state file existence and content
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"cache_name": "stateFileCache123"}
        
        mock_client_instance = MockGenaiClient.return_value
        mock_cache_get_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_get_result.name = "cachedContents/stateFileCache123"
        mock_cache_get_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.get.return_value = mock_cache_get_result

        result_cache_name = get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(result_cache_name, "cachedContents/stateFileCache123")
        mock_client_instance.caches.get.assert_called_once_with(name="cachedContents/stateFileCache123")

    @patch("services.llm.cache_service.os.path.exists")
    @patch("services.llm.cache_service.open", new_callable=mock_open)
    @patch("services.llm.cache_service.json.load")
    @patch("services.llm.cache_service.genai.Client")
    def test_retrieve_cache_expired_creates_new(
        self, MockGenaiClient, mock_json_load, mock_file_open, mock_path_exists
    ):
        """Test that an expired cache triggers creation of a new one."""
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"cache_name": "expiredCache"}

        mock_client_instance = MockGenaiClient.return_value
        
        # Mock get returning an expired cache
        mock_expired_cache = MagicMock(spec=genai_types.CachedContent)
        mock_expired_cache.name = "cachedContents/expiredCache"
        mock_expired_cache.model = f"models/{settings.LLM_MODEL_NAME}"
        # Set expire_time to the past
        mock_expired_cache.expire_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_client_instance.caches.get.return_value = mock_expired_cache

        # Mock create returning a new cache
        mock_new_cache = MagicMock(spec=genai_types.CachedContent)
        mock_new_cache.name = "cachedContents/newFreshCache"
        mock_new_cache.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.create.return_value = mock_new_cache

        result_cache_name = get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(result_cache_name, "cachedContents/newFreshCache")
        # Should have tried to get the old one
        mock_client_instance.caches.get.assert_called_once()
        # Should have created a new one
        mock_client_instance.caches.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()

