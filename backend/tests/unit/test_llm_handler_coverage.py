import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.config import settings
from llm_handler import generate_report_from_content


class TestLLMHandlerCoverage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_api_key = settings.GEMINI_API_KEY
        self.original_model_name = settings.LLM_MODEL_NAME
        self.original_fallback_model = settings.LLM_FALLBACK_MODEL_NAME
        
        settings.GEMINI_API_KEY = "test-api-key"
        settings.LLM_MODEL_NAME = "gemini-pro-test"
        settings.LLM_FALLBACK_MODEL_NAME = "gemini-flash-test"

    def tearDown(self):
        settings.GEMINI_API_KEY = self.original_api_key
        settings.LLM_MODEL_NAME = self.original_model_name
        settings.LLM_FALLBACK_MODEL_NAME = self.original_fallback_model

    @patch("llm_handler.genai.Client")
    @patch("llm_handler.cache_service.get_or_create_prompt_cache")
    @patch("llm_handler.file_upload_service.upload_vision_files")
    @patch("llm_handler.prompt_builder_service.build_prompt_parts")
    @patch("llm_handler.generation_service.build_generation_config")
    @patch("llm_handler.generation_service.generate_with_retry")
    @patch("llm_handler.generation_service.calculate_cost")
    @patch("llm_handler.response_parser_service.parse_llm_response")
    @patch("llm_handler.file_upload_service.cleanup_uploaded_files")
    async def test_generate_report_happy_path_with_cache(
        self,
        mock_cleanup,
        mock_parse,
        mock_calc_cost,
        mock_generate,
        mock_build_config,
        mock_build_prompt,
        mock_upload,
        mock_get_cache,
        mock_client_cls,
    ):
        """Test successful report generation with cache."""
        # Setup mocks
        mock_get_cache.return_value = "cachedContents/test-cache"
        mock_upload.return_value = ([], ["file1"], [])
        mock_build_prompt.return_value = ["prompt"]
        
        mock_config = MagicMock()
        mock_config.cached_content = "cachedContents/test-cache"
        mock_build_config.return_value = mock_config
        
        mock_response = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150
        mock_response.usage_metadata.cached_content_token_count = 80
        mock_generate.return_value = mock_response
        
        mock_calc_cost.return_value = 0.0125
        mock_parse.return_value = "Generated Report"

        # Execute
        report, cost, tokens = await generate_report_from_content(
            processed_files=[{"type": "text"}], additional_text="extra"
        )

        # Verify
        self.assertEqual(report, "Generated Report")
        self.assertEqual(cost, 0.0125)
        self.assertEqual(tokens["prompt_token_count"], 100)
        self.assertEqual(tokens["cached_content_token_count"], 80)
        
        # Verify cache was used
        mock_get_cache.assert_called_once()
        # Verify generation called
        mock_generate.assert_called_once()
        
        # Verify cleanup
        mock_cleanup.assert_called_once()

    @patch("llm_handler.genai.Client")
    @patch("llm_handler.cache_service.get_or_create_prompt_cache")
    @patch("llm_handler.file_upload_service.upload_vision_files")
    @patch("llm_handler.prompt_builder_service.build_prompt_parts")
    @patch("llm_handler.generation_service.build_generation_config")
    @patch("llm_handler.generation_service.generate_with_retry")
    @patch("llm_handler.generation_service.calculate_cost")
    @patch("llm_handler.response_parser_service.parse_llm_response")
    @patch("llm_handler.file_upload_service.cleanup_uploaded_files")
    async def test_generate_report_no_cache(
        self,
        mock_cleanup,
        mock_parse,
        mock_calc_cost,
        mock_generate,
        mock_build_config,
        mock_build_prompt,
        mock_upload,
        mock_get_cache,
        mock_client_cls,
    ):
        """Test successful report generation without cache."""
        # Setup mocks
        mock_get_cache.return_value = None  # No cache
        mock_upload.return_value = ([], [], [])
        mock_build_prompt.return_value = ["prompt"]
        
        mock_config = MagicMock()
        mock_config.cached_content = None
        mock_build_config.return_value = mock_config
        
        mock_response = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150
        mock_response.usage_metadata.cached_content_token_count = 0
        mock_generate.return_value = mock_response
        
        mock_calc_cost.return_value = 0.015
        mock_parse.return_value = "Generated Report"

        # Execute
        report, cost, tokens = await generate_report_from_content(
            processed_files=[{"type": "text"}]
        )

        # Verify
        self.assertEqual(report, "Generated Report")
        self.assertEqual(cost, 0.015)
        mock_generate.assert_called_once()

    def test_api_key_missing(self):
        """Test early exit when API key is missing."""
        settings.GEMINI_API_KEY = None
        
        # We need to run this in an async loop since the function is async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        report, cost, tokens = loop.run_until_complete(
            generate_report_from_content([])
        )
        loop.close()
        
        self.assertIn("API key missing", report)
        self.assertEqual(cost, 0.0)
        self.assertEqual(tokens, {})
