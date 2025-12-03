import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Literal

from google import genai
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, Field
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    AsyncRetrying
)

from app.core.config import settings
# Assuming these services are refactored to be cleaner dependencies
from app.services.llm import (
    cache_service,
    file_upload_service,
    generation_service,
    prompt_builder_service,
    response_parser_service,
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 1. Strict Typing (Contracts)
# -----------------------------------------------------------------------------
class ProcessedFile(BaseModel):
    """Contract for file inputs to the LLM."""
    filename: str
    file_type: str = Field(alias="type") # Map 'type' from dict to 'file_type'
    content: Optional[bytes] = None
    gcs_uri: Optional[str] = None
    
    # Allow extra fields for compatibility with existing dicts if needed
    model_config = {"extra": "ignore", "populate_by_name": True}

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    candidate_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

class ReportResult(BaseModel):
    content: str
    usage: TokenUsage

class LLMGenerationError(Exception):
    """Base exception for LLM failures."""
    pass

# -----------------------------------------------------------------------------
# 2. The Gemini Service
# -----------------------------------------------------------------------------
class GeminiReportGenerator:
    """
    Orchestrates insurance report generation using Google Gemini 2.5.
    Handles Multimodal inputs, Context Caching, and Resilience patterns.
    """

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            # raise ValueError("GEMINI_API_KEY is not configured.")
            # Don't crash on init if key is missing (e.g. during tests), just log
            logger.error("GEMINI_API_KEY is not configured.")
        
        # Initialize client once (Singleton pattern via module instantiation)
        # Assuming google.genai.Client is thread-safe (it usually is)
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            self.client = None
        
        # Retry policy: Exponential backoff for transient errors
        self.retry_policy = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((
                google_exceptions.ServiceUnavailable,
                google_exceptions.TooManyRequests,
                google_exceptions.InternalServerError
            )),
            reraise=True
        )

    async def generate(
        self, 
        processed_files: List[ProcessedFile], 
        additional_text: str = ""
    ) -> ReportResult:
        """
        Main entry point for report generation.
        """
        if not self.client:
             raise LLMGenerationError("LLM service is not configured (API key missing).")

        uploaded_files = []
        uploaded_names = []
        
        try:
            # 1. Context Caching (Optimization)
            # Run in threadpool if cache_service is blocking/heavy
            cache_name = await asyncio.to_thread(
                cache_service.get_or_create_prompt_cache, self.client
            )
            use_cache = bool(cache_name)
            
            logger.info(f"Report Gen Start. Files: {len(processed_files)} | Cache: {use_cache}")

            # 2. Upload Vision Assets (PDFs/Images)
            # We explicitly map the Pydantic models to what the service expects
            # Note: Ideally refactor file_upload_service to accept ProcessedFile objects
            # For now, convert back to dict for compatibility with existing services
            file_dicts = [f.model_dump(by_alias=True) for f in processed_files]
            
            uploaded_files, uploaded_names, upload_errors = await file_upload_service.upload_vision_files(
                self.client, file_dicts
            )

            # 3. Execute Generation Strategy (The "waterfall")
            response = await self._execute_generation_strategy(
                processed_files=file_dicts, # Legacy service support
                additional_text=additional_text,
                uploaded_files=uploaded_files,
                upload_errors=upload_errors,
                cache_name=cache_name
            )

            # 4. Parse Response
            report_text = response_parser_service.parse_llm_response(response)
            
            # 5. Extract Metrics
            usage = self._extract_usage(response)
            
            return ReportResult(content=report_text, usage=usage)

        except Exception as e:
            logger.error(f"LLM Generation Failed: {e}", exc_info=True)
            raise LLMGenerationError(f"Report generation failed: {str(e)}") from e
            
        finally:
            # 6. Cleanup (Best Effort)
            if uploaded_names:
                asyncio.create_task(
                    self._cleanup_files_safely(uploaded_names)
                )

    async def _execute_generation_strategy(
        self,
        processed_files: List[Dict],
        additional_text: str,
        uploaded_files: List[Any],
        upload_errors: List[str],
        cache_name: Optional[str]
    ) -> Any:
        """
        Implements the fallback waterfall:
        1. Primary Model + Cache
        2. Primary Model + No Cache (if Cache Invalid)
        3. Fallback Model + No Cache (if Primary Overloaded)
        """
        
        # Helper to build prompt
        def get_prompt_parts(use_cache: bool):
            return prompt_builder_service.build_prompt_parts(
                processed_files=processed_files,
                additional_text=additional_text,
                uploaded_file_objects=uploaded_files,
                upload_error_messages=upload_errors,
                use_cache=use_cache
            )

        # --- Attempt 1: Primary + Cache ---
        if cache_name:
            try:
                logger.debug("Attempt 1: Primary Model with Cache")
                return await self._generate_call(
                    model_name=settings.LLM_MODEL_NAME,
                    contents=get_prompt_parts(use_cache=True),
                    cache_name=cache_name
                )
            except Exception as e:
                # Detect Cache Invalidation (400 or specific Google error)
                if self._is_cache_error(e):
                    logger.warning(f"Cache invalidated ({e}). Falling back to no-cache.")
                else:
                    # If it's an overload/server error, we might want to skip to fallback
                    if self._is_overload_error(e):
                         logger.warning(f"Primary model overloaded ({e}). Skipping to fallback.")
                         return await self._attempt_fallback(get_prompt_parts(False))
                    raise e # Retrying same config won't help for other errors

        # --- Attempt 2: Primary + No Cache ---
        try:
            logger.debug("Attempt 2: Primary Model without Cache")
            return await self._generate_call(
                model_name=settings.LLM_MODEL_NAME,
                contents=get_prompt_parts(use_cache=False),
                cache_name=None
            )
        except Exception as e:
            if self._is_overload_error(e) and settings.LLM_FALLBACK_MODEL_NAME:
                logger.warning(f"Primary model overloaded ({e}). Switching to Fallback.")
                return await self._attempt_fallback(get_prompt_parts(False))
            raise e

    async def _attempt_fallback(self, prompt_parts: List[Any]) -> Any:
        """Executes the request against the fallback model."""
        if not settings.LLM_FALLBACK_MODEL_NAME:
            raise LLMGenerationError("Primary model failed and no fallback configured.")
            
        logger.info(f"Attempt 3: Fallback Model ({settings.LLM_FALLBACK_MODEL_NAME})")
        return await self._generate_call(
            model_name=settings.LLM_FALLBACK_MODEL_NAME,
            contents=prompt_parts,
            cache_name=None
        )

    async def _generate_call(self, model_name: str, contents: List[Any], cache_name: Optional[str]) -> Any:
        """Executes the actual API call wrapped in the retry policy."""
        config = generation_service.build_generation_config(cache_name)
        
        async for attempt in self.retry_policy:
            with attempt:
                return await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )

    async def _cleanup_files_safely(self, file_names: List[str]):
        """Background cleanup task that doesn't block the response."""
        try:
            await file_upload_service.cleanup_uploaded_files(self.client, file_names)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

    def _is_cache_error(self, e: Exception) -> bool:
        """Heuristic to check for 400 Invalid Argument related to cache."""
        s_e = str(e)
        return "INVALID_ARGUMENT" in s_e or "400" in s_e

    def _is_overload_error(self, e: Exception) -> bool:
        """Heuristic to check for 503 or Overloaded."""
        s_e = str(e).lower()
        return "503" in s_e or "overloaded" in s_e

    def _extract_usage(self, response: Any) -> TokenUsage:
        """Safe extraction of token usage."""
        meta = getattr(response, "usage_metadata", None)
        if not meta:
            return TokenUsage()
        
        return TokenUsage(
            prompt_tokens=getattr(meta, "prompt_token_count", 0),
            candidate_tokens=getattr(meta, "candidates_token_count", 0),
            total_tokens=getattr(meta, "total_token_count", 0),
            cached_tokens=getattr(meta, "cached_content_token_count", 0),
        )

# Singleton Instance (Optional, depending on DI framework)
gemini_generator = GeminiReportGenerator()
