import os
import shutil
from abc import ABC, abstractmethod
from google.cloud import storage
from werkzeug.datastructures import FileStorage

class StorageProvider(ABC):
    """The Interface (Contract) that respects DIP."""
    @abstractmethod
    def save(self, file_data: bytes, filename: str, folder: str) -> str:
        pass

class LocalStorage(StorageProvider):
    """Implementation for your local laptop."""
    def __init__(self, base_path: str = "temp_uploads"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def save(self, file_data: bytes, filename: str, folder: str) -> str:
        # Respects local file system logic
        target_dir = os.path.join(self.base_path, folder)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, filename)
        with open(path, "wb") as f:
            f.write(file_data)
        return path

class GoogleCloudStorage(StorageProvider):
    """Implementation for Cloud Run."""
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def save(self, file_data: bytes, filename: str, folder: str) -> str:
        # Respects Blob logic
        blob_path = f"{folder}/{filename}"
        blob = self.bucket.blob(blob_path)
        blob.upload_from_string(file_data)
        # Return the gs:// URI or a signed URL depending on your needs
        return f"gs://{self.bucket_name}/{blob_path}"

# The Factory (KISS)
def get_storage_provider() -> StorageProvider:
    # Check if running in Cloud Run (usually has K_SERVICE env var) or explicit PROD flag
    if os.getenv("K_SERVICE") or os.getenv("ENVIRONMENT") == "production":
        bucket_name = os.getenv("STORAGE_BUCKET_NAME")
        if not bucket_name:
             # Fallback or error if bucket not set in prod
             raise ValueError("STORAGE_BUCKET_NAME must be set in production")
        return GoogleCloudStorage(bucket_name=bucket_name)
    
    # Default to local
    return LocalStorage()
