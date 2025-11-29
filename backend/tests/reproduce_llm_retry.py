
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google import genai
from core.config import settings

# Import the function to test
from llm_handler import generate_report_from_content

class TestLLMRetryLogic(unittest.TestCase):
    def setUp(self):
        # Patch settings
        self.settings_patcher = patch('llm_handler.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.GEMINI_API_KEY = "fake_key"
        self.mock_settings.LLM_MODEL_NAME = "primary-model"
        self.mock_settings.LLM_FALLBACK_MODEL_NAME = "fallback-model"
        
        # Patch dependencies
        self.client_patcher = patch('llm_handler.genai.Client')
        self.mock_client_cls = self.client_patcher.start()
        self.mock_client = self.mock_client_cls.return_value
        
        self.cache_service_patcher = patch('llm_handler.cache_service')
        self.mock_cache_service = self.cache_service_patcher.start()
        
        self.file_upload_patcher = patch('llm_handler.file_upload_service')
        self.mock_file_upload = self.file_upload_patcher.start()
        self.mock_file_upload.upload_vision_files = AsyncMock(return_value=([], [], []))
        self.mock_file_upload.cleanup_uploaded_files = AsyncMock()
        
        self.prompt_builder_patcher = patch('llm_handler.prompt_builder_service')
        self.mock_prompt_builder = self.prompt_builder_patcher.start()
        self.mock_prompt_builder.build_prompt_parts.return_value = ["prompt"]
        
        self.generation_service_patcher = patch('llm_handler.generation_service')
        self.mock_generation_service = self.generation_service_patcher.start()
        self.mock_generation_service.build_generation_config.return_value = {}
        self.mock_generation_service.calculate_cost.return_value = 0.0
        
        self.response_parser_patcher = patch('llm_handler.response_parser_service')
        self.mock_response_parser = self.response_parser_patcher.start()
        self.mock_response_parser.parse_llm_response.return_value = "Parsed Report"

    def tearDown(self):
        self.settings_patcher.stop()
        self.client_patcher.stop()
        self.cache_service_patcher.stop()
        self.file_upload_patcher.stop()
        self.prompt_builder_patcher.stop()
        self.generation_service_patcher.stop()
        self.response_parser_patcher.stop()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_success_first_try(self):
        """Test success on the first attempt (with cache)."""
        self.mock_cache_service.get_or_create_prompt_cache.return_value = "cache-name"
        self.mock_generation_service.generate_with_retry = AsyncMock(return_value=MagicMock())
        
        result, cost, tokens = self.run_async(generate_report_from_content([], ""))
        
        self.assertEqual(result, "Parsed Report")
        # Verify called with cache
        self.mock_generation_service.generate_with_retry.assert_called_once()
        args, kwargs = self.mock_generation_service.generate_with_retry.call_args
        self.assertEqual(kwargs['model'], "primary-model")
        # We can't easily check config content without more mocking, but we know it tried once.

    def test_cache_error_then_success(self):
        """Test Cache Error -> Retry No Cache -> Success."""
        self.mock_cache_service.get_or_create_prompt_cache.return_value = "cache-name"
        
        # First call raises ClientError (Invalid Argument - Cache), Second succeeds
        error = genai.errors.ClientError("400 INVALID_ARGUMENT", {})
        error.status_code = 400
        
        self.mock_generation_service.generate_with_retry = AsyncMock(side_effect=[error, MagicMock()])
        
        result, cost, tokens = self.run_async(generate_report_from_content([], ""))
        
        self.assertEqual(result, "Parsed Report")
        self.assertEqual(self.mock_generation_service.generate_with_retry.call_count, 2)
        
        # Check args for second call (No Cache)
        args2, kwargs2 = self.mock_generation_service.generate_with_retry.call_args_list[1]
        self.assertEqual(kwargs2['model'], "primary-model")
        # Should imply no cache config passed

    def test_overload_error_then_fallback(self):
        """Test Overload Error -> Fallback Model -> Success."""
        self.mock_cache_service.get_or_create_prompt_cache.return_value = None # No cache to start
        
        # First call raises ServerError (Overloaded), Second succeeds
        error = genai.errors.ServerError("503 Service Unavailable", {})
        
        self.mock_generation_service.generate_with_retry = AsyncMock(side_effect=[error, MagicMock()])
        
        result, cost, tokens = self.run_async(generate_report_from_content([], ""))
        
        self.assertEqual(result, "Parsed Report")
        self.assertEqual(self.mock_generation_service.generate_with_retry.call_count, 2)
        
        # Check args for second call (Fallback)
        args2, kwargs2 = self.mock_generation_service.generate_with_retry.call_args_list[1]
        self.assertEqual(kwargs2['model'], "fallback-model")

    def test_cache_error_then_overload_then_fallback(self):
        """Test Cache Error -> Retry No Cache -> Overload -> Fallback -> Success."""
        self.mock_cache_service.get_or_create_prompt_cache.return_value = "cache-name"
        
        cache_error = genai.errors.ClientError("400 INVALID_ARGUMENT", {})
        cache_error.status_code = 400
        
        overload_error = genai.errors.ServerError("503 Service Unavailable", {})
        
        # 1. Cache Error
        # 2. Retry No Cache -> Overload Error
        # 3. Retry Fallback -> Success
        self.mock_generation_service.generate_with_retry = AsyncMock(side_effect=[cache_error, overload_error, MagicMock()])
        
        result, cost, tokens = self.run_async(generate_report_from_content([], ""))
        
        self.assertEqual(result, "Parsed Report")
        self.assertEqual(self.mock_generation_service.generate_with_retry.call_count, 3)
        
        # 1st: Primary + Cache
        # 2nd: Primary + No Cache
        # 3rd: Fallback + No Cache
        args3, kwargs3 = self.mock_generation_service.generate_with_retry.call_args_list[2]
        self.assertEqual(kwargs3['model'], "fallback-model")

if __name__ == '__main__':
    unittest.main()
