import datetime
from functools import lru_cache

import google.auth
from google.auth.transport import requests
from google.cloud import storage

from app.core.config import settings


@lru_cache(maxsize=1)
def get_storage_client():
    return storage.Client()


def get_signing_credentials():
    """
    Get credentials for signing URLs in Cloud Run environment.

    Cloud Run's compute engine credentials don't have a private key,
    so we need to use IAM SignBlob API via service_account_email + access_token.

    NOTE: Intentionally not cached because tokens expire (~1 hour).
    """
    credentials, project = google.auth.default()

    # Refresh credentials to ensure we have a valid token
    auth_req = requests.Request()
    credentials.refresh(auth_req)

    # Get service account email - compute engine credentials have this attribute
    signing_email = getattr(credentials, "service_account_email", None)
    if not signing_email:
        # Fallback: construct the default compute SA email
        signing_email = f"{project}-compute@developer.gserviceaccount.com"

    return signing_email, credentials


def generate_upload_signed_url(
    filename: str, content_type: str, organization_id: str, case_id: str
) -> dict:
    """
    Generates a secure V4 Signed URL.
    The frontend uses this URL to PUT the file directly to Google Cloud Storage.

    Uses IAM SignBlob API for Cloud Run environments where credentials lack private keys.
    """
    client = get_storage_client()
    bucket = client.bucket(settings.STORAGE_BUCKET_NAME)

    # Organize files by organization_id and case_id to prevent collisions and separate tenant data
    # Example: uploads/org_123/case_456/document.pdf
    blob_name = f"uploads/{organization_id}/{case_id}/{filename}"
    blob = bucket.blob(blob_name)

    # Get signing credentials for IAM SignBlob API
    signing_email, credentials = get_signing_credentials()

    # Generate the URL using IAM SignBlob API
    url = blob.generate_signed_url(
        version="v4",
        # Allow PUT requests (uploads)
        method="PUT",
        # URL valid for 15 minutes
        expiration=datetime.timedelta(minutes=15),
        content_type=content_type,
        # Enforce size limit at the GCS ingress layer to prevent "Infinite Cost" attacks
        headers={"x-goog-content-length-range": f"0,{settings.MAX_FILE_SIZE_BYTES}"},
        # Use IAM SignBlob API instead of local signing
        service_account_email=signing_email,
        access_token=credentials.token,
    )

    return {
        "upload_url": url,
        "gcs_path": f"gs://{settings.STORAGE_BUCKET_NAME}/{blob_name}",
        "file_path": blob_name,
    }


MAX_DOWNLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB Limit


def download_file_to_temp(gcs_path: str, local_path: str):
    """
    Downloads a file from GCS to a local path (used by the worker later).
    Enforces strict security checks: Bucket Validation and Size Limits.
    """
    client = get_storage_client()

    # Parse gs://bucket/path
    if gcs_path.startswith("gs://"):
        path_parts = gcs_path.replace("gs://", "").split("/", 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1]
    else:
        # Fallback if just the path is passed
        bucket_name = settings.STORAGE_BUCKET_NAME
        blob_name = gcs_path

    # 1. SECURITY: Strict Bucket Validation
    # Prevent Path Traversal / Malicious Bucket Attacks
    if bucket_name != settings.STORAGE_BUCKET_NAME:
        raise ValueError(
            f"Security Alert: Attempted download from unauthorized bucket '{bucket_name}'. Expected '{settings.STORAGE_BUCKET_NAME}'."
        )

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # 2. RELOAD METADATA to get size
    blob.reload()

    # 3. SECURITY: Size Limit (DoS/OOM Protection)
    if blob.size and blob.size > MAX_DOWNLOAD_SIZE_BYTES:
        raise ValueError(
            f"File too large for processing: {blob.size} bytes (Max: {MAX_DOWNLOAD_SIZE_BYTES} bytes)."
        )

    blob.download_to_filename(local_path)
    return local_path


def generate_download_signed_url(gcs_path: str) -> str:
    """
    Generates a secure V4 Signed URL for downloading a file.
    Valid for 15 minutes.

    Uses IAM SignBlob API for Cloud Run environments where credentials lack private keys.
    """
    client = get_storage_client()

    # Parse gs://bucket_name/blob_name
    if not gcs_path.startswith("gs://"):
        raise ValueError("Invalid GCS path format")

    path_parts = gcs_path.replace("gs://", "").split("/", 1)
    bucket_name = path_parts[0]
    blob_name = path_parts[1]

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Get signing credentials for IAM SignBlob API
    signing_email, credentials = get_signing_credentials()

    url = blob.generate_signed_url(
        version="v4",
        method="GET",
        expiration=datetime.timedelta(minutes=15),
        # Use IAM SignBlob API instead of local signing
        service_account_email=signing_email,
        access_token=credentials.token,
    )

    return url


def tag_blob_as_finalized(gcs_path: str):
    """
    Tags a blob with metadata to prevent lifecycle policy deletion.

    This marks successfully registered files as 'finalized', protecting them
    from automatic cleanup by the GCS lifecycle policy that removes orphaned
    uploads after 24 hours.

    Args:
        gcs_path: Full GCS path (e.g., "uploads/org_id/case_id/file.pdf")
    """
    client = get_storage_client()
    bucket = client.bucket(settings.STORAGE_BUCKET_NAME)

    # Clean path: remove gs://bucket/ prefix if present
    clean_path = gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")

    blob = bucket.blob(clean_path)

    # Set metadata to mark as registered/finalized
    blob.metadata = {"status": "finalized"}
    blob.patch()  # Update only metadata without re-uploading the file


def delete_blob(gcs_path: str) -> bool:
    """
    Deletes a blob from GCS.

    Args:
        gcs_path: Full GCS path (e.g., "gs://bucket/uploads/org_id/case_id/file.pdf")

    Returns:
        True if deleted, False if blob didn't exist.
    """
    client = get_storage_client()

    # Parse gs://bucket_name/blob_name
    if gcs_path.startswith("gs://"):
        path_parts = gcs_path.replace("gs://", "").split("/", 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1] if len(path_parts) > 1 else ""
    else:
        bucket_name = settings.STORAGE_BUCKET_NAME
        blob_name = gcs_path

    # Security: Validate bucket
    if bucket_name != settings.STORAGE_BUCKET_NAME:
        raise ValueError(f"Cannot delete from unauthorized bucket: {bucket_name}")

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if blob.exists():
        blob.delete()
        return True
    return False


def gcs_blob_exists(gcs_uri: str) -> tuple[bool, str | None]:
    """
    Check if a blob exists in GCS.

    Used for pre-flight validation before passing URIs to Gemini API
    to prevent INVALID_ARGUMENT errors from non-existent files.

    Args:
        gcs_uri: Full GCS path (e.g., "gs://bucket/path/to/file.pdf")

    Returns:
        tuple[bool, str | None]: (exists, error_reason)
        - If True, reason is None
        - If False, reason contains "Not Found" or specific exception/error message
    """
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return False, "Invalid URI format"

    try:
        client = get_storage_client()
        path_parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1] if len(path_parts) > 1 else ""

        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if blob.exists():
            return True, None
        return False, "Not Found"

    except Exception as e:
        # Capture specific permission/network errors
        return False, str(e)
