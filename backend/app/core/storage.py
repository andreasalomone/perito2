import logging
import posixpath
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Union

from google.api_core.exceptions import GoogleAPICallError

# Google Cloud Imports
# Google Cloud Imports
from google.cloud import storage  # type: ignore[attr-defined]

from app.core.config import settings

# Configure structured logging
logger = logging.getLogger("app.storage")


class StorageException(Exception):
    """Base exception for storage related errors."""

    pass


class StorageProvider(ABC):
    """
    Abstract Base Class for file storage operations.
    Follows the Dependency Inversion Principle.
    """

    @abstractmethod
    def save(
        self, file_stream: Union[bytes, BinaryIO], filename: str, folder: str
    ) -> str:
        """
        Saves a file to the storage backend.

        Args:
            file_stream: Raw bytes or a file-like object (preferred for memory efficiency).
            filename: The name of the file (e.g., 'report.docx').
            folder: The logical directory/prefix (e.g., 'reports/123').

        Returns:
            The unique identifier or URI of the saved file.
        """
        pass


class LocalStorage(StorageProvider):
    """
    Local filesystem implementation for Development environments.
    """

    def __init__(self, base_path: str = "temp_uploads"):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _safe_join(self, folder: str, filename: str) -> Path:
        """
        Prevents Path Traversal attacks by ensuring the final path
        is within the base directory.
        """
        # Ensure inputs are relative to avoid discarding base_path
        if Path(folder).is_absolute():
            folder = folder.lstrip("/")
        if Path(filename).is_absolute():
            filename = filename.lstrip("/")

        target_file = (self.base_path / folder / filename).resolve()

        # Security Check: Resolve and compare parents
        try:
            target_file.relative_to(self.base_path)
        except ValueError:
            logger.warning(
                f"Security Alert: Path traversal attempt detected: {folder}/{filename}"
            )
            raise StorageException("Invalid file path.")

        return target_file

    def save(
        self, file_stream: Union[bytes, BinaryIO], filename: str, folder: str
    ) -> str:
        try:
            target_path = self._safe_join(folder, filename)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "wb") as f:
                if isinstance(file_stream, bytes):
                    f.write(file_stream)
                else:
                    # Stream copy (efficient for large files)
                    import shutil

                    # Seek to start only if the stream supports it
                    if hasattr(file_stream, "seekable") and file_stream.seekable():
                        file_stream.seek(0)
                    shutil.copyfileobj(file_stream, f)

            logger.info(f"File saved locally: {target_path}")
            return str(target_path)

        except OSError as e:
            logger.error(f"Local storage write failed: {e}")
            raise StorageException(f"Failed to save file locally: {e}")


class GoogleCloudStorage(StorageProvider):
    """
    Production implementation using Google Cloud Storage.
    """

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        # Client is retrieved via singleton pattern externally or initialized once
        self._client = get_gcs_client()
        self._bucket = self._client.bucket(bucket_name)

    def save(
        self, file_stream: Union[bytes, BinaryIO], filename: str, folder: str
    ) -> str:
        # Security: sanitize filename to prevent path traversal
        filename = posixpath.basename(filename)

        # Use posixpath for consistent cloud keys (forward slashes) regardless of OS
        blob_path = posixpath.join(folder, filename)
        blob = self._bucket.blob(blob_path)

        try:
            if isinstance(file_stream, bytes):
                blob.upload_from_string(
                    file_stream, content_type="application/octet-stream"
                )
            else:
                # Seek to start only if the stream supports it
                if hasattr(file_stream, "seekable") and file_stream.seekable():
                    file_stream.seek(0)
                blob.upload_from_file(
                    file_stream, content_type="application/octet-stream"
                )

            logger.info(f"File saved to GCS: gs://{self.bucket_name}/{blob_path}")
            return f"gs://{self.bucket_name}/{blob_path}"

        except GoogleAPICallError as e:
            logger.error(f"GCS upload failed: {e}")
            raise StorageException(f"Failed to upload to Cloud Storage: {e}")


# -----------------------------------------------------------------------------
# Dependency Injection & Factory
# -----------------------------------------------------------------------------


@lru_cache()
def get_gcs_client() -> storage.Client:
    """
    Singleton provider for the GCS Client.
    Utilizes connection pooling for performance.
    """
    return storage.Client()


def get_storage_provider() -> StorageProvider:
    """
    Factory to return the appropriate storage provider based on environment.
    """
    # Use RUN_LOCALLY from settings to determine environment
    if not settings.RUN_LOCALLY:
        if not settings.STORAGE_BUCKET_NAME:
            logger.critical("Configuration Error: STORAGE_BUCKET_NAME is missing.")
            raise ValueError("STORAGE_BUCKET_NAME must be set in production")

        return GoogleCloudStorage(bucket_name=settings.STORAGE_BUCKET_NAME)

    # Default to local storage for dev/test
    # We use a distinct folder inside the project to avoid clutter
    return LocalStorage(base_path="local_data/uploads")
