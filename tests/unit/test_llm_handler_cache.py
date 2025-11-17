import os

# Temporarily adjust sys.path to import from the parent directory (project root)
# This is often needed if tests are in a subdirectory and modules are in the root or other subdirectories.
# In a more structured project, you might use a proper test runner setup or __init__.py files.
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

# Assuming the test file is in tests/unit/ and the core module is in the parent directory's core/
# This adds the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from google.api_core import exceptions as google_exceptions
from google.genai import (
    types as genai_types,  # Renamed to avoid conflict with unittest.mock.types
)

# Now that sys.path is adjusted, we can import from the project
from core.config import settings
from core.prompt_config import (
    PREDEFINED_STYLE_REFERENCE_TEXT,
    REPORT_STRUCTURE_PROMPT,
    SYSTEM_INSTRUCTION,
)

# The module and function to test
# Assuming llm_handler is at the root of the project or correctly in PYTHONPATH
# If llm_handler.py is in the project root, this should work after sys.path adjustment
from llm_handler import _get_or_create_prompt_cache  # Target function


class TestGetOrCreatePromptCache(unittest.TestCase):

    def setUp(self):
        """Set up for each test method."""
        # Store original settings to restore them later, preventing test side-effects
        self.original_cache_name = settings.REPORT_PROMPT_CACHE_NAME
        self.original_model_name = settings.LLM_MODEL_NAME
        self.original_cache_ttl_days = settings.CACHE_TTL_DAYS
        self.original_cache_display_name = settings.CACHE_DISPLAY_NAME
        self.original_retry_attempts = settings.LLM_API_RETRY_ATTEMPTS
        self.original_retry_wait = settings.LLM_API_RETRY_WAIT_SECONDS

        # Set default test values (can be overridden in specific tests)
        settings.LLM_MODEL_NAME = "gemini-test-model"
        settings.CACHE_TTL_DAYS = 1
        settings.CACHE_DISPLAY_NAME = "TestCacheDisplayName"
        settings.REPORT_PROMPT_CACHE_NAME = None  # Default to no existing cache
        settings.LLM_API_RETRY_ATTEMPTS = 1  # Deterministic tests (no retries)
        settings.LLM_API_RETRY_WAIT_SECONDS = 0

    def tearDown(self):
        """Clean up after each test method."""
        settings.REPORT_PROMPT_CACHE_NAME = self.original_cache_name
        settings.LLM_MODEL_NAME = self.original_model_name
        settings.CACHE_TTL_DAYS = self.original_cache_ttl_days
        settings.CACHE_DISPLAY_NAME = self.original_cache_display_name
        settings.LLM_API_RETRY_ATTEMPTS = self.original_retry_attempts
        settings.LLM_API_RETRY_WAIT_SECONDS = self.original_retry_wait

    @patch("llm_handler.genai.Client")
    def test_create_cache_success_no_existing_name(self, MockGenaiClient):
        """Test successful cache creation when no REPORT_PROMPT_CACHE_NAME is set."""
        settings.REPORT_PROMPT_CACHE_NAME = None

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/newlyCreatedCache123"
        mock_cache_create_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_cache_create_result.expire_time = "2025-01-01T00:00:00Z"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        expected_ttl_seconds = settings.CACHE_TTL_DAYS * 24 * 60 * 60
        expected_ttl_string = f"{expected_ttl_seconds}s"

        result_cache_name = _get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(result_cache_name, "cachedContents/newlyCreatedCache123")
        mock_client_instance.caches.create.assert_called_once()
        call_args = mock_client_instance.caches.create.call_args
        self.assertEqual(call_args[1]["model"], settings.LLM_MODEL_NAME)
        self.assertEqual(call_args[1]["config"]["ttl"], expected_ttl_string)
        self.assertEqual(
            call_args[1]["config"]["display_name"], settings.CACHE_DISPLAY_NAME
        )
        self.assertIn(
            PREDEFINED_STYLE_REFERENCE_TEXT,
            call_args[1]["config"]["contents"][0].parts[0].text,
        )
        self.assertIn(
            REPORT_STRUCTURE_PROMPT, call_args[1]["config"]["contents"][1].parts[0].text
        )
        self.assertIn(
            SYSTEM_INSTRUCTION,
            call_args[1]["config"]["system_instruction"].parts[0].text,
        )
        mock_client_instance.caches.get.assert_not_called()

    @patch("llm_handler.genai.Client")
    def test_create_cache_api_error(self, MockGenaiClient):
        """Test handling of API error during cache creation."""
        settings.REPORT_PROMPT_CACHE_NAME = None
        mock_client_instance = MockGenaiClient.return_value
        mock_client_instance.caches.create.side_effect = (
            google_exceptions.InternalServerError("Creation failed via API")
        )

        result_cache_name = _get_or_create_prompt_cache(mock_client_instance)

        self.assertIsNone(result_cache_name)
        mock_client_instance.caches.create.assert_called_once()
        mock_client_instance.caches.get.assert_not_called()

    @patch("llm_handler.genai.Client")
    def test_retrieve_cache_success(self, MockGenaiClient):
        """Test successful retrieval of an existing, valid cache."""
        existing_cache_id = "cachedContents/existingValidCache456"
        settings.REPORT_PROMPT_CACHE_NAME = existing_cache_id
        settings.LLM_MODEL_NAME = "retrieved-model"  # ensure it matches

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_get_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_get_result.name = existing_cache_id
        mock_cache_get_result.model = (
            f"models/{settings.LLM_MODEL_NAME}"  # Matches current model
        )
        mock_client_instance.caches.get.return_value = mock_cache_get_result

        result_cache_name = _get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(result_cache_name, existing_cache_id)
        mock_client_instance.caches.get.assert_called_once_with(name=existing_cache_id)
        mock_client_instance.caches.create.assert_not_called()

    @patch("llm_handler.genai.Client")
    def test_retrieve_cache_not_found_then_create(self, MockGenaiClient):
        """Test creation of a new cache if existing one is not found."""
        settings.REPORT_PROMPT_CACHE_NAME = "cachedContents/nonExistentCache789"

        mock_client_instance = MockGenaiClient.return_value
        mock_client_instance.caches.get.side_effect = google_exceptions.NotFound(
            "Cache not found"
        )

        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/newlyCreatedAfterNotFound"
        mock_cache_create_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        result_cache_name = _get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(result_cache_name, "cachedContents/newlyCreatedAfterNotFound")
        mock_client_instance.caches.get.assert_called_once_with(
            name="cachedContents/nonExistentCache789"
        )
        mock_client_instance.caches.create.assert_called_once()

    @patch("llm_handler.genai.Client")
    def test_retrieve_cache_different_model_then_create(self, MockGenaiClient):
        """Test creation of a new cache if existing one is for a different model."""
        existing_cache_id = "cachedContents/differentModelCache321"
        settings.REPORT_PROMPT_CACHE_NAME = existing_cache_id
        settings.LLM_MODEL_NAME = "current-app-model"

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_get_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_get_result.name = existing_cache_id
        mock_cache_get_result.model = "models/some-other-model"  # Different model
        mock_client_instance.caches.get.return_value = mock_cache_get_result

        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/newlyCreatedAfterModelMismatch"
        mock_cache_create_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        result_cache_name = _get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(
            result_cache_name, "cachedContents/newlyCreatedAfterModelMismatch"
        )
        mock_client_instance.caches.get.assert_called_once_with(name=existing_cache_id)
        mock_client_instance.caches.create.assert_called_once()
        self.assertEqual(
            mock_client_instance.caches.create.call_args[1]["model"],
            "current-app-model",
        )

    @patch("llm_handler.genai.Client")
    def test_retrieve_cache_other_error_then_create(self, MockGenaiClient):
        """Test creation of new cache if retrieval causes a generic error."""
        settings.REPORT_PROMPT_CACHE_NAME = "cachedContents/errorCache654"

        mock_client_instance = MockGenaiClient.return_value
        mock_client_instance.caches.get.side_effect = Exception(
            "Some generic retrieval error"
        )

        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/newlyCreatedAfterGenericError"
        mock_cache_create_result.model = f"models/{settings.LLM_MODEL_NAME}"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        result_cache_name = _get_or_create_prompt_cache(mock_client_instance)

        self.assertEqual(
            result_cache_name, "cachedContents/newlyCreatedAfterGenericError"
        )
        mock_client_instance.caches.get.assert_called_once_with(
            name="cachedContents/errorCache654"
        )
        mock_client_instance.caches.create.assert_called_once()

    @patch("llm_handler.genai.Client")
    def test_model_name_stripping_for_creation(self, MockGenaiClient):
        """Test that 'models/' prefix is stripped from LLM_MODEL_NAME for cache creation."""
        settings.REPORT_PROMPT_CACHE_NAME = None
        settings.LLM_MODEL_NAME = (
            "models/gemini-test-model-with-prefix"  # Model name with prefix
        )
        expected_model_id_for_creation = "gemini-test-model-with-prefix"

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/strippedModelNameCache"
        mock_cache_create_result.model = (
            f"models/{expected_model_id_for_creation}"  # API returns with prefix
        )
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        _get_or_create_prompt_cache(mock_client_instance)

        mock_client_instance.caches.create.assert_called_once()
        call_args = mock_client_instance.caches.create.call_args
        # Assert that the model ID passed to client.caches.create() does NOT have the prefix
        self.assertEqual(call_args[1]["model"], expected_model_id_for_creation)

    @patch("llm_handler.genai.Client")
    def test_model_name_no_prefix_for_creation(self, MockGenaiClient):
        """Test that model name without prefix is used as-is for cache creation."""
        settings.REPORT_PROMPT_CACHE_NAME = None
        settings.LLM_MODEL_NAME = (
            "gemini-test-model-no-prefix"  # Model name without prefix
        )
        expected_model_id_for_creation = "gemini-test-model-no-prefix"

        mock_client_instance = MockGenaiClient.return_value
        mock_cache_create_result = MagicMock(spec=genai_types.CachedContent)
        mock_cache_create_result.name = "cachedContents/noPrefixModelNameCache"
        mock_cache_create_result.model = f"models/{expected_model_id_for_creation}"
        mock_client_instance.caches.create.return_value = mock_cache_create_result

        _get_or_create_prompt_cache(mock_client_instance)

        mock_client_instance.caches.create.assert_called_once()
        call_args = mock_client_instance.caches.create.call_args
        self.assertEqual(call_args[1]["model"], expected_model_id_for_creation)


if __name__ == "__main__":
    unittest.main()
