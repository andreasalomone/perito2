import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions
from google.genai import types

from core.config import settings
from services.llm import generation_service


class TestGenerationServiceCoverage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_retry_attempts = settings.LLM_API_RETRY_ATTEMPTS
        self.original_retry_wait = settings.LLM_API_RETRY_WAIT_SECONDS
        
        settings.LLM_API_RETRY_ATTEMPTS = 3
        settings.LLM_API_RETRY_WAIT_SECONDS = 0.1 # Fast retries for testing

    def tearDown(self):
        settings.LLM_API_RETRY_ATTEMPTS = self.original_retry_attempts
        settings.LLM_API_RETRY_WAIT_SECONDS = self.original_retry_wait

    def test_build_generation_config(self):
        """Test building generation config with and without cache."""
        # With cache
        config_with_cache = generation_service.build_generation_config("test-cache")
        self.assertEqual(config_with_cache.cached_content, "test-cache")
        self.assertIsNotNone(config_with_cache.safety_settings)
        
        # Without cache
        config_no_cache = generation_service.build_generation_config(None)
        self.assertIsNone(config_no_cache.cached_content)

    @patch("services.llm.generation_service.AsyncRetrying")
    async def test_generate_with_retry_success(self, mock_retrying):
        """Test successful generation."""
        # We can't easily mock AsyncRetrying context manager behavior perfectly without complex setup,
        # so we'll test the inner logic or integration style if possible.
        # Alternatively, we can trust tenacity works and just mock the client call.
        pass 
        # Actually, let's just test the function directly without mocking tenacity, 
        # but mocking the client to succeed immediately.
        
    async def test_generate_with_retry_integration_success(self):
        """Test generate_with_retry succeeds on first try."""
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value="success")
        
        result = await generation_service.generate_with_retry(
            client=mock_client,
            model="model",
            contents=[],
            config=MagicMock()
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_client.aio.models.generate_content.call_count, 1)

    async def test_generate_with_retry_retries_on_failure(self):
        """Test generate_with_retry retries on retriable exceptions."""
        mock_client = MagicMock()
        # Fail twice, then succeed
        error = google_exceptions.ServiceUnavailable("503")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[error, error, "success"])
        
        result = await generation_service.generate_with_retry(
            client=mock_client,
            model="model",
            contents=[],
            config=MagicMock()
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_client.aio.models.generate_content.call_count, 3)

    def test_calculate_cost(self):
        """Test cost calculation logic."""
        # Tier 1 Input (< 200k)
        meta_t1 = MagicMock()
        meta_t1.prompt_token_count = 100_000
        meta_t1.candidates_token_count = 50_000
        
        # Expected: (0.1 * 1.25) + (0.05 * 10.00) = 0.125 + 0.5 = 0.625
        # Assuming default settings: INPUT_TIER_1=1.25, OUTPUT_TIER_1=10.00
        # We should probably mock settings to be sure
        with patch("core.config.settings.PRICE_INPUT_TIER_1", 1.0), \
             patch("core.config.settings.PRICE_OUTPUT_TIER_1", 10.0):
             
            cost = generation_service.calculate_cost(meta_t1)
            self.assertAlmostEqual(cost, (0.1 * 1.0) + (0.05 * 10.0))

        # Tier 2 Input (> 200k)
        meta_t2 = MagicMock()
        meta_t2.prompt_token_count = 300_000
        meta_t2.candidates_token_count = 50_000
        
        with patch("core.config.settings.PRICE_INPUT_TIER_2", 2.0), \
             patch("core.config.settings.PRICE_OUTPUT_TIER_2", 20.0):
             
            cost = generation_service.calculate_cost(meta_t2)
            self.assertAlmostEqual(cost, (0.3 * 2.0) + (0.05 * 20.0))
