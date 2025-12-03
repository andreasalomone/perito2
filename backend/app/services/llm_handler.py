import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
# Cleanup Retry Queue Infrastructure
# -----------------------------------------------------------------------------

@dataclass
class CleanupRetryItem:
    """Represents a file cleanup operation pending retry."""
    file_names: List[str]
    attempt: int = 0
    max_attempts: int = 3
    next_retry_at: datetime = field(default_factory=datetime.now)
    first_failed_at: datetime = field(default_factory=datetime.now)
    last_error: Optional[str] = None
    
    def should_retry(self) -> bool:
        """Check if this item should be retried."""
        return (
            self.attempt < self.max_attempts and 
            datetime.now() >= self.next_retry_at
        )
    
    def calculate_next_retry(self) -> datetime:
        """Exponential backoff: 2^attempt minutes."""
        wait_minutes = 2 ** self.attempt  # 1, 2, 4 minutes
        return datetime.now() + timedelta(minutes=wait_minutes)

class CleanupRetryQueue:
    """Manages retry queue for failed Gemini File API cleanup operations."""
    
    def __init__(self):
        self.queue: deque[CleanupRetryItem] = deque()
        self.dead_letter: List[CleanupRetryItem] = []
        self._processing = False
        
    def enqueue(self, file_names: List[str], error: str):
        """Add failed cleanup to retry queue."""
        item = CleanupRetryItem(
            file_names=file_names,
            attempt=0,
            next_retry_at=datetime.now() + timedelta(minutes=1),  # First retry after 1 min
            last_error=error
        )
        self.queue.append(item)
        logger.info(f"Enqueued {len(file_names)} files for cleanup retry")
        
    def move_to_dead_letter(self, item: CleanupRetryItem):
        """Move persistently failing cleanup to dead letter queue."""
        self.dead_letter.append(item)
        logger.error(
            f"Moved {len(item.file_names)} files to dead-letter queue after {item.attempt} attempts. "
            f"Files: {item.file_names[:3]}...",
            extra={
                "alert": True,
                "dead_letter_file_count": len(item.file_names),
                "dead_letter_files": item.file_names,
                "attempts": item.attempt,
                "first_failed_at": item.first_failed_at.isoformat(),
                "last_error": item.last_error
            }
        )
    
    async def process_queue(self, client: genai.Client):
        """Process items in the retry queue."""
        if self._processing:
            return  # Prevent concurrent processing
            
        self._processing = True
        try:
            items_to_retry = []
            
            # Collect items ready for retry
            while self.queue:
                item = self.queue.popleft()
                if item.should_retry():
                    items_to_retry.append(item)
                else:
                    # Not ready yet, re-enqueue
                    self.queue.append(item)
                    break  # Items are ordered by retry time
            
            # Process retries
            for item in items_to_retry:
                item.attempt += 1
                logger.info(f"Retrying cleanup attempt {item.attempt}/{item.max_attempts} for {len(item.file_names)} files")
                
                try:
                    # Attempt cleanup
                    success_count, fail_count = await file_upload_service.cleanup_uploaded_files(
                        client, item.file_names
                    )
                    
                    if fail_count == 0:
                        logger.info(f"Retry successful: cleaned up {success_count} files")
                    else:
                        # Partial failure - update file list and retry
                        item.last_error = f"Partial failure: {fail_count}/{len(item.file_names)} failed"
                        
                        if item.attempt >= item.max_attempts:
                            self.move_to_dead_letter(item)
                        else:
                            item.next_retry_at = item.calculate_next_retry()
                            self.queue.append(item)
                            
                except Exception as e:
                    item.last_error = str(e)
                    
                    if item.attempt >= item.max_attempts:
                        self.move_to_dead_letter(item)
                    else:
                        item.next_retry_at = item.calculate_next_retry()
                        self.queue.append(item)
                        logger.warning(f"Cleanup retry {item.attempt} failed, will retry at {item.next_retry_at}")
        finally:
            self._processing = False

# Global retry queue instance
cleanup_retry_queue = CleanupRetryQueue()

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
        processed_files: List[ProcessedFile]
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
            # Create UploadCandidate objects for the new service API
            upload_candidates = [
                file_upload_service.UploadCandidate(
                    file_path=f.gcs_uri or f.filename, # Fallback if gcs_uri is missing, though logic might need review
                    mime_type=f.file_type,
                    display_name=f.filename,
                    is_vision_asset=(f.file_type != "application/json") # Simple heuristic, adjust as needed
                )
                for f in processed_files
            ]
            
            # The new API returns a list of FileOperationResult objects
            upload_results = await file_upload_service.upload_vision_files_batch(
                self.client, upload_candidates
            )

            # Process results
            uploaded_files = [res.gemini_file for res in upload_results if res.success]
            uploaded_names = [res.file_name for res in upload_results if res.success]
            upload_errors = [res.error_message for res in upload_results if not res.success]

            # 3. Execute Generation Strategy (The "waterfall")
            # Convert ProcessedFile back to dict for legacy service support in prompt builder
            file_dicts = [f.model_dump(by_alias=True) for f in processed_files]
            
            response = await self._execute_generation_strategy(
                processed_files=file_dicts,
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
            # We need the actual file names (resource names) from the uploaded files for deletion
            # The FileOperationResult.file_name is the display name, but we need the resource name for deletion?
            # Wait, file_upload_service.delete_single_file takes `file_name`. 
            # In the old code: `temp_uploaded_file_names_for_api.append(result.name)` which is the resource name (files/...)
            # In the new code: `FileOperationResult` has `gemini_file` which has `.name`.
            
            resource_names_to_delete = [
                f.name for f in uploaded_files if f and f.name
            ]
            
            if resource_names_to_delete:
                asyncio.create_task(
                    self._cleanup_files_safely(resource_names_to_delete)
                )

    async def _execute_generation_strategy(
        self,
        processed_files: List[Dict],
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
        """
        Background cleanup task with retry queue and dead-letter handling.
        
        CRITICAL: Cleanup failures are a quota/cost risk. The Gemini File API has storage quotas.
        If cleanup consistently fails, we will hit quota limits and block new uploads.
        
        IMPLEMENTATION: Uses exponential backoff retry queue (1min, 2min, 4min)
        and moves persistent failures to dead-letter queue for manual intervention.
        """
        try:
            success_count, fail_count = await file_upload_service.cleanup_uploaded_files(
                self.client, file_names
            )
            
            if fail_count == 0:
                logger.info(f"Successfully cleaned up {len(file_names)} Gemini API files")
            else:
                # Partial failure - enqueue failed files for retry
                error_msg = f"Partial cleanup failure: {fail_count}/{len(file_names)} files failed"
                logger.warning(error_msg)
                cleanup_retry_queue.enqueue(file_names, error_msg)
                
        except Exception as e:
            # Complete failure - enqueue all files for retry
            error_msg = f"Gemini File API cleanup failed: {str(e)}"
            logger.error(
                f"CRITICAL: {error_msg} for {len(file_names)} files. "
                f"Enqueuing for retry. Files: {file_names[:3]}...",
                exc_info=True,
                extra={
                    "alert": True,
                    "failed_file_count": len(file_names),
                    "failed_files": file_names,
                    "error_type": type(e).__name__
                }
            )
            cleanup_retry_queue.enqueue(file_names, error_msg)
        
        # Process retry queue in background (non-blocking)
        asyncio.create_task(cleanup_retry_queue.process_queue(self.client))

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
