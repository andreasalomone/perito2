import asyncio
import heapq
import logging
import mimetypes

try:
    import magic  # python-magic for MIME type detection via magic bytes

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Protocol, Set, Tuple

# Google GenAI imports (Assumed installed)
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import errors as genai_errors

# Use pydantic v2
from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helper: Retry Predicate
# -----------------------------------------------------------------------------
def _is_retryable_error(e: BaseException) -> bool:
    """
    Determines if an exception should trigger a retry.
    Handles both legacy google.api_core exceptions and new google.genai SDK errors.
    """
    # 1. New Google GenAI SDK Errors (Primary for new calls)
    if isinstance(e, genai_errors.ServerError):
        # Retry all Server Errors (5xx)
        return True

    if isinstance(e, genai_errors.ClientError):
        # Retry specific Client Errors (429 Resource Exhausted)
        if e.code == 429:
            return True

    # 2. Legacy Google API Core Exceptions (Keep for backward compatibility)
    if isinstance(
        e,
        (
            google_exceptions.ServiceUnavailable,
            google_exceptions.TooManyRequests,
            google_exceptions.InternalServerError,
        ),
    ):
        return True

    return False


# -----------------------------------------------------------------------------
# 1. Protocols & Contracts
# -----------------------------------------------------------------------------


class FileUploadServiceProtocol(Protocol):
    @dataclass
    class UploadCandidate:
        file_path: str
        mime_type: str
        display_name: str
        is_vision_asset: bool
        gcs_uri: Optional[str] = None

    @dataclass
    class FileOperationResult:
        success: bool
        gemini_file: Any
        file_name: str
        error_message: Optional[str]

    async def upload_vision_files_batch(
        self, client: genai.Client, candidates: List[UploadCandidate]
    ) -> List[FileOperationResult]: ...

    async def cleanup_uploaded_files(
        self, client: genai.Client, file_names: List[str]
    ) -> Tuple[int, int]: ...


class CacheServiceProtocol(Protocol):
    def get_or_create_prompt_cache(self, client: genai.Client) -> Optional[str]: ...


class PromptBuilderServiceProtocol(Protocol):
    def build_prompt_parts(
        self,
        processed_files: List[Dict[str, Any]],
        uploaded_file_objects: List[Any],
        upload_error_messages: List[str],
        use_cache: bool,
    ) -> List[Any]: ...


class ResponseParserServiceProtocol(Protocol):
    def parse_llm_response(self, response: Any) -> str: ...


class GenerationServiceProtocol(Protocol):
    def build_generation_config(self, cache_name: Optional[str]) -> Any: ...


# -----------------------------------------------------------------------------
# 2. Data Models
# -----------------------------------------------------------------------------


class ProcessedFile(BaseModel):
    """
    Contract for file inputs to the LLM.
    Strict validation prevents passing arbitrary system paths.
    """

    filename: str
    file_type: str = Field(alias="type")  # Category label: "vision", "text", "error"
    mime_type: Optional[str] = None  # Actual MIME type: "application/pdf", "image/jpeg"
    content: Optional[str] = None  # Text content for text files (changed from bytes)
    gcs_uri: Optional[str] = None
    local_path: Optional[str] = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


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


class SecurityError(Exception):
    """Raised when file path validation fails."""

    pass


# -----------------------------------------------------------------------------
# 3. Robust Retry Queue (Memory Safe)
# -----------------------------------------------------------------------------


@dataclass(order=True)
class CleanupRetryItem:
    """
    Represents a file cleanup operation pending retry.
    Ordered by next_retry_at for priority queue efficiency.
    """

    next_retry_at: datetime
    file_names: List[str] = field(compare=False)
    attempt: int = field(default=0, compare=False)
    max_attempts: int = field(default=3, compare=False)

    # Do not compare these fields in the heap
    first_failed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), compare=False
    )
    last_error: Optional[str] = field(default=None, compare=False)

    def calculate_next_retry(self) -> datetime:
        """Exponential backoff: 2^attempt minutes."""
        wait_minutes = 2**self.attempt
        return datetime.now(timezone.utc) + timedelta(minutes=wait_minutes)


# ... (imports)


class CleanupRetryQueue:
    """
    Manages retry queue for failed Gemini File API cleanup operations.
    Thread-safe and uses WeakSet to track background tasks to prevent GC.
    """

    def __init__(self, max_dead_letter_size: int = 100):
        self._queue: List[CleanupRetryItem] = []  # Heapq structure
        self._dead_letter: Deque[CleanupRetryItem] = deque(maxlen=max_dead_letter_size)
        self._lock = asyncio.Lock()  # Async-native lock for event loop compatibility
        # Track background tasks to prevent premature GC
        self._background_tasks: Set[asyncio.Task] = set()

    async def enqueue(self, file_names: List[str], error: str) -> None:
        """Add failed cleanup to retry queue."""
        if not file_names:
            return

        item = CleanupRetryItem(
            file_names=file_names,
            attempt=0,
            next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=1),
            last_error=error,
        )
        async with self._lock:
            heapq.heappush(self._queue, item)

        # Log count only, avoid leaking PII (filenames)
        logger.info(f"Enqueued {len(file_names)} files for cleanup retry.")

    async def _move_to_dead_letter(self, item: CleanupRetryItem) -> None:
        self._dead_letter.append(item)
        logger.error(
            f"Moved {len(item.file_names)} files to dead-letter queue. "
            f"Last error: {item.last_error}",
            extra={"alert": True},
        )

    async def process_queue(
        self, client: genai.Client, file_upload_service: FileUploadServiceProtocol
    ) -> None:
        """
        Process items in the retry queue.
        Uses a lock to ensure single-consumer behavior per instance.
        """
        if self._lock.locked():
            # If already processing, we skip this trigger.
            # Ideally, we would set a 'dirty' flag to re-run, but for this
            # simple implementation, skipping is acceptable as long as
            # triggers are frequent.
            return

        async with self._lock:
            now = datetime.now(timezone.utc)
            items_to_retry: List[CleanupRetryItem] = []

            # 1. Pop all items ready for retry
            while self._queue:
                if self._queue[0].next_retry_at <= now:
                    items_to_retry.append(heapq.heappop(self._queue))
                else:
                    break

        # 2. Process outside the lock
        # This allows new items to be enqueued while we process current batch
        for item in items_to_retry:
            await self._attempt_cleanup(client, file_upload_service, item)

    async def _attempt_cleanup(
        self,
        client: genai.Client,
        service: FileUploadServiceProtocol,
        item: CleanupRetryItem,
    ) -> None:
        item.attempt += 1
        try:
            _, fail_count = await service.cleanup_uploaded_files(
                client, item.file_names
            )

            if fail_count > 0:
                await self._handle_failure(
                    item, f"Partial failure: {fail_count} failed"
                )
            else:
                logger.info(f"Retry successful for {len(item.file_names)} files.")

        except Exception as e:
            await self._handle_failure(item, str(e))

    async def _handle_failure(self, item: CleanupRetryItem, error_msg: str) -> None:
        item.last_error = error_msg
        if item.attempt >= item.max_attempts:
            await self._move_to_dead_letter(item)
        else:
            item.next_retry_at = item.calculate_next_retry()
            async with self._lock:
                heapq.heappush(self._queue, item)

    def create_background_task(self, coro) -> None:
        """
        Safe wrapper for fire-and-forget tasks.
        Keeps a strong reference to the task until completion.
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)


# -----------------------------------------------------------------------------
# 4. The Gemini Service
# -----------------------------------------------------------------------------


class GeminiReportGenerator:
    """
    Orchestrates insurance report generation using Google Gemini.
    """

    def __init__(
        self,
        client: genai.Client,  # Inject Client directly
        model_name: str,
        fallback_model_name: Optional[str],
        file_upload_service: FileUploadServiceProtocol,
        cache_service: CacheServiceProtocol,
        prompt_builder_service: PromptBuilderServiceProtocol,
        response_parser_service: ResponseParserServiceProtocol,
        generation_service: GenerationServiceProtocol,
        retry_queue: CleanupRetryQueue,
        allowed_file_dirs: Optional[List[Path]] = None,
        concurrency_limit: int = 5,  # Encapsulated: controls max parallel LLM calls
    ):
        self.client = client
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name

        self.file_upload_service = file_upload_service
        self.cache_service = cache_service
        self.prompt_builder_service = prompt_builder_service
        self.response_parser_service = response_parser_service
        self.generation_service = generation_service
        self.retry_queue = retry_queue

        # Security: Default to empty list (deny all) if not provided
        self.allowed_file_dirs = allowed_file_dirs or []

        # Concurrency control: limits parallel LLM API calls per instance
        self._semaphore = asyncio.Semaphore(concurrency_limit)

        self.retry_policy = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(_is_retryable_error),
            reraise=True,
        )

    async def generate(self, processed_files: List[ProcessedFile]) -> ReportResult:
        """Main entry point for report generation."""
        # Cost Safeguard: Limit concurrent executions via instance semaphore
        async with self._semaphore:
            return await self._generate_internal(processed_files)

    async def _generate_internal(
        self, processed_files: List[ProcessedFile]
    ) -> ReportResult:
        """Internal generation logic (protected by semaphore)."""
        vision_parts: List[Any] = (
            []
        )  # Combined: types.Part (GCS) + types.File (uploaded)
        upload_errors: List[str] = []
        cache_name: Optional[str] = None

        try:
            # 1. Context Caching
            cache_name = self.cache_service.get_or_create_prompt_cache(self.client)

            # 2. Prepare Vision Assets (async for non-blocking I/O)
            # Separate GCS files (use Part.from_uri) from local files (upload)
            gcs_candidates, upload_candidates, skipped_errors = (
                await self._prepare_vision_assets(processed_files)
            )
            # Add skipped file errors so they appear in the prompt for user awareness
            upload_errors.extend(skipped_errors)

            # 2a. GCS Direct Parts - No download/upload needed
            from app.services.llm.file_upload_service import create_gcs_direct_part

            for candidate in gcs_candidates:
                try:
                    part = create_gcs_direct_part(
                        candidate.gcs_uri, candidate.mime_type
                    )
                    vision_parts.append(part)
                    logger.debug(
                        f"Created GCS direct part for: {candidate.display_name}"
                    )
                except Exception as e:
                    error_msg = (
                        f"GCS direct access failed for {candidate.display_name}: {e}"
                    )
                    logger.warning(error_msg)
                    upload_errors.append(error_msg)

            # 2b. Upload non-GCS files to Gemini Files API
            if upload_candidates:
                upload_results = (
                    await self.file_upload_service.upload_vision_files_batch(
                        self.client, upload_candidates
                    )
                )
                uploaded_files = [
                    res.gemini_file for res in upload_results if res.success
                ]
                vision_parts.extend(uploaded_files)
                upload_errors.extend(
                    [
                        res.error_message
                        for res in upload_results
                        if not res.success and res.error_message
                    ]
                )
            else:
                uploaded_files = []

            # 3. Execute Generation
            file_dicts = [f.model_dump(by_alias=True) for f in processed_files]

            response = await self._execute_generation_strategy(
                processed_files=file_dicts,
                uploaded_files=vision_parts,  # Now contains both Part and File objects
                upload_errors=upload_errors,
                cache_name=cache_name,
            )

            # 4. Parse & Extract
            report_text = self.response_parser_service.parse_llm_response(response)
            usage = self._extract_usage(response)

            return ReportResult(content=report_text, usage=usage)

        except Exception as e:
            logger.error(f"LLM Generation Failed: {e}", exc_info=True)
            raise LLMGenerationError(f"Report generation failed: {str(e)}") from e

        finally:
            # 5. Cleanup - Only for uploaded files (not GCS direct parts)
            # Filter to get only types.File objects (have 'name' attribute)
            files_to_cleanup = [f for f in vision_parts if hasattr(f, "name")]
            self._schedule_cleanup(files_to_cleanup)

    # Vertex AI supported MIME types for vision assets
    VERTEX_SUPPORTED_MIME_TYPES = frozenset(
        {
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        }
    )

    async def _prepare_vision_assets(
        self, processed_files: List[ProcessedFile]
    ) -> Tuple[
        List[FileUploadServiceProtocol.UploadCandidate],
        List[FileUploadServiceProtocol.UploadCandidate],
        List[str],  # Added: skipped file errors for user visibility
    ]:
        """
        Separates vision assets into two groups:
        1. GCS Direct: Files with GCS URIs that can use Part.from_uri()
        2. Upload Required: Local-only files that need Gemini Files API upload

        Returns:
            Tuple of (gcs_candidates, upload_candidates, skipped_errors)
        """
        gcs_candidates = []
        upload_candidates = []
        skipped_errors = []

        for f in processed_files:
            local_path = f.local_path
            gcs_uri = f.gcs_uri

            if not local_path and not gcs_uri:
                continue

            # SECURITY: Strict path validation for local files (async, non-blocking)
            if local_path and not await self._is_safe_path(local_path):
                logger.warning(
                    f"Skipping unsafe or unauthorized file path: {local_path}",
                    extra={"security_event": True},
                )
                skipped_errors.append(f"Skipped '{f.filename}': invalid file path")
                continue

            # Only process vision assets (skip JSON/Text that goes into prompt)
            # Note: file_type is the category ("vision", "text", "error"), not MIME type
            if f.file_type not in ("vision",):
                continue

            # SECURITY: For local files, use magic bytes to detect true MIME type
            # This prevents MIME spoofing attacks (e.g., exe renamed to jpg)
            actual_mime_type: Optional[str] = None
            if local_path:
                actual_mime_type = await self._validate_magic_bytes(local_path)

            # Fallback: If magic detection unavailable/failed, use extension-based
            if not actual_mime_type:
                actual_mime_type = f.mime_type
                if not actual_mime_type or actual_mime_type in (
                    "vision",
                    "application/octet-stream",
                ):
                    guessed_type, _ = mimetypes.guess_type(f.filename or "")
                    if guessed_type:
                        actual_mime_type = guessed_type
                    else:
                        ext = (f.filename or "").lower().rsplit(".", 1)[-1]
                        ext_map = {
                            "jpg": "image/jpeg",
                            "jpeg": "image/jpeg",
                            "png": "image/png",
                            "gif": "image/gif",
                            "webp": "image/webp",
                            "pdf": "application/pdf",
                        }
                        actual_mime_type = ext_map.get(ext)

            # STRICT VALIDATION: Skip files with unsupported MIME types
            if (
                not actual_mime_type
                or actual_mime_type not in self.VERTEX_SUPPORTED_MIME_TYPES
            ):
                logger.warning(
                    f"Skipping '{f.filename}': unsupported MIME type '{actual_mime_type}'. "
                    f"Vertex AI requires: {self.VERTEX_SUPPORTED_MIME_TYPES}"
                )
                skipped_errors.append(
                    f"Skipped '{f.filename}': unsupported file type "
                    f"(got '{actual_mime_type or 'unknown'}')"
                )
                continue

            candidate = self.file_upload_service.UploadCandidate(
                file_path=local_path or gcs_uri,
                mime_type=actual_mime_type,
                display_name=f.filename,
                is_vision_asset=True,
                gcs_uri=gcs_uri,
            )

            # If we have a GCS URI, use Part.from_uri() (no download needed)
            # Otherwise, fall back to Gemini Files API upload
            if gcs_uri:
                gcs_candidates.append(candidate)
                logger.debug(f"GCS direct access for: {f.filename}")
            else:
                upload_candidates.append(candidate)
                logger.debug(f"Upload required for: {f.filename}")

        logger.info(
            f"Vision assets: {len(gcs_candidates)} GCS direct, "
            f"{len(upload_candidates)} upload required, {len(skipped_errors)} skipped"
        )
        return gcs_candidates, upload_candidates, skipped_errors

    async def _prepare_upload_candidates(
        self, processed_files: List[ProcessedFile]
    ) -> List[FileUploadServiceProtocol.UploadCandidate]:
        """DEPRECATED: Use _prepare_vision_assets instead."""
        _, upload_candidates, _ = await self._prepare_vision_assets(processed_files)
        return upload_candidates

    def _is_safe_path_sync(self, path_str: str) -> bool:
        """
        Synchronous path validation. Run via asyncio.to_thread() to avoid blocking.
        Validates that the path is within the allowed directories.
        Prevents Directory Traversal attacks.
        """
        if not self.allowed_file_dirs:
            # If no dirs are explicitly allowed, fail open safe (deny everything)
            return False

        try:
            target_path = Path(path_str).resolve()

            # Check against whitelist
            for allowed in self.allowed_file_dirs:
                # resolve allowed path to ensure we compare absolute paths
                allowed_abs = allowed.resolve()
                if target_path.is_relative_to(allowed_abs):
                    return target_path.exists()

            return False
        except Exception:
            return False

    async def _is_safe_path(self, path_str: str) -> bool:
        """Async wrapper for path validation. Offloads blocking I/O to thread pool."""
        return await asyncio.to_thread(self._is_safe_path_sync, path_str)

    def _validate_magic_bytes_sync(self, path: str) -> Optional[str]:
        """
        Returns real MIME type if in whitelist, else None.
        Ignores browser's claimed MIME type - trusts magic bytes only.
        """
        if not MAGIC_AVAILABLE:
            return None  # Fall back to extension-based detection
        try:
            real_mime = magic.from_file(path, mime=True)
            if real_mime in self.VERTEX_SUPPORTED_MIME_TYPES:
                return real_mime
            return None
        except Exception:
            return None

    async def _validate_magic_bytes(self, path: str) -> Optional[str]:
        """Async wrapper for magic byte validation."""
        return await asyncio.to_thread(self._validate_magic_bytes_sync, path)

    async def _execute_generation_strategy(
        self,
        processed_files: List[Dict[str, Any]],
        uploaded_files: List[Any],
        upload_errors: List[str],
        cache_name: Optional[str],
    ) -> Any:

        # Helper to regenerate prompt parts based on strategy
        def get_prompt_parts(use_cache: bool) -> List[Any]:
            return self.prompt_builder_service.build_prompt_parts(
                processed_files=processed_files,
                uploaded_file_objects=uploaded_files,
                upload_error_messages=upload_errors,
                use_cache=use_cache,
            )

        # Strategy 1: Primary Model + Cache
        if cache_name:
            try:
                return await self._generate_call(
                    model_name=self.model_name,
                    contents=get_prompt_parts(use_cache=True),
                    cache_name=cache_name,
                )
            except Exception as e:
                if self._is_cache_error(e):
                    logger.warning(f"Cache invalidated ({e}). Retry without cache.")
                elif self._is_overload_error(e):
                    logger.warning(f"Primary overloaded ({e}). Fallback strategy.")
                    return await self._attempt_fallback(get_prompt_parts(False))
                else:
                    raise e

        # Strategy 2: Primary Model + No Cache (or cache failed)
        try:
            return await self._generate_call(
                model_name=self.model_name,
                contents=get_prompt_parts(use_cache=False),
                cache_name=None,
            )
        except Exception as e:
            if self._is_overload_error(e) and self.fallback_model_name:
                logger.warning(f"Primary overloaded ({e}). Fallback strategy.")
                return await self._attempt_fallback(get_prompt_parts(False))
            raise e

    async def _attempt_fallback(self, prompt_parts: List[Any]) -> Any:
        if not self.fallback_model_name:
            raise LLMGenerationError("Primary model failed and no fallback configured.")

        return await self._generate_call(
            model_name=self.fallback_model_name,
            contents=prompt_parts,
            cache_name=None,
        )

    async def _generate_call(
        self, model_name: str, contents: List[Any], cache_name: Optional[str]
    ) -> Any:
        config = self.generation_service.build_generation_config(cache_name)

        async for attempt in self.retry_policy:
            with attempt:
                # Use aio (async) interface explicitly
                return await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )

    def _schedule_cleanup(self, uploaded_files: List[Any]) -> None:
        """Schedules cleanup of uploaded files using the robust queue."""
        resource_names = [
            f.name for f in uploaded_files if f and getattr(f, "name", None)
        ]
        if not resource_names:
            return

        async def _cleanup_task():
            try:
                # Attempt immediate cleanup
                _, fail = await self.file_upload_service.cleanup_uploaded_files(
                    self.client, resource_names
                )
                if fail > 0:
                    # Enqueue partial failures
                    await self.retry_queue.enqueue(
                        resource_names, f"Partial failure: {fail} failed"
                    )
            except Exception as e:
                # Enqueue total failures
                logger.error(f"Initial cleanup failed: {e}")
                await self.retry_queue.enqueue(resource_names, str(e))

            # Process queue (tries to clear backlog)
            await self.retry_queue.process_queue(self.client, self.file_upload_service)

        # Use the queue's safe task wrapper
        self.retry_queue.create_background_task(_cleanup_task())

    def _is_cache_error(self, e: Exception) -> bool:
        s_e = str(e)
        return "INVALID_ARGUMENT" in s_e or "400" in s_e

    def _is_overload_error(self, e: Exception) -> bool:
        s_e = str(e).lower()
        return "503" in s_e or "overloaded" in s_e

    def _extract_usage(self, response: Any) -> TokenUsage:
        """Safe extraction of token usage."""
        meta = getattr(response, "usage_metadata", None)
        if not meta:
            return TokenUsage()

        # NOTE: Vertex AI SDK may return explicit None for some fields (not missing),
        # so getattr's default won't help. Use 'or 0' to coalesce None -> 0.
        return TokenUsage(
            prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            candidate_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            total_tokens=getattr(meta, "total_token_count", 0) or 0,
            cached_tokens=getattr(meta, "cached_content_token_count", 0) or 0,
        )


# -----------------------------------------------------------------------------
# 5. Dependency Injection & Singleton Factory (Compatibility Layer)
# -----------------------------------------------------------------------------

from app.core.config import settings
from app.services.llm import (
    cache_service,
    file_upload_service,
    generation_service,
    prompt_builder_service,
    response_parser_service,
)

# Global retry queue instance
cleanup_retry_queue = CleanupRetryQueue()


# Singleton Instance
# We construct it with the concrete services from the app
# AND inject the client and allowed dirs
# Singleton Factory: Lazy Loading Proxy
# prevents application startup crash if API Key is missing (e.g. CI/CD)
class LazyGeminiProxy:
    def __init__(self):
        self._delegate: Optional[GeminiReportGenerator] = None
        self._lock = asyncio.Lock()

    async def generate(self, *args, **kwargs) -> ReportResult:
        instance = await self._get_instance()
        return await instance.generate(*args, **kwargs)

    async def _get_instance(self) -> GeminiReportGenerator:
        if self._delegate:
            return self._delegate

        async with self._lock:
            # Double-check locking pattern
            if self._delegate:
                return self._delegate

            # GEMINI_API_KEY check removed - Vertex AI uses ADC (Application Default Credentials)
            # which are automatically available in Cloud Run

            logger.info("Initializing Gemini Service via Vertex AI (Lazy Load)...")

            # Create Client - Use Vertex AI mode for direct GCS access
            try:
                _client = genai.Client(
                    vertexai=True,
                    project=settings.GOOGLE_CLOUD_PROJECT,
                    location=settings.GEMINI_API_LOCATION,
                )
            except Exception as e:
                logger.critical(f"Failed to create Vertex AI Client: {e}")
                raise

            # Create Generator
            self._delegate = GeminiReportGenerator(
                client=_client,
                model_name=settings.LLM_MODEL_NAME,
                fallback_model_name=settings.LLM_FALLBACK_MODEL_NAME,
                file_upload_service=file_upload_service,
                cache_service=cache_service,
                prompt_builder_service=prompt_builder_service,
                response_parser_service=response_parser_service,
                generation_service=generation_service,
                retry_queue=cleanup_retry_queue,
                allowed_file_dirs=[Path(settings.UPLOAD_FOLDER), Path("/tmp")],
                concurrency_limit=settings.GEMINI_CONCURRENCY,
            )
            return self._delegate


# Export the proxy as the singleton
gemini_generator = LazyGeminiProxy()
