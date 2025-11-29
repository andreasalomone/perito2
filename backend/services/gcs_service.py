import datetime
from google.cloud import storage
from config import settings

def get_storage_client():
    return storage.Client()

def generate_upload_signed_url(
    filename: str, 
    content_type: str, 
    organization_id: str
) -> dict:
    """
    Generates a secure V4 Signed URL. 
    The frontend uses this URL to PUT the file directly to Google Cloud Storage.
    """
    client = get_storage_client()
    bucket = client.bucket(settings.STORAGE_BUCKET_NAME)
    
    # Organize files by organization_id to prevent collisions and separate tenant data
    # Example: uploads/org_123/2025-11-29_report.pdf
    blob_name = f"uploads/{organization_id}/{filename}"
    blob = bucket.blob(blob_name)

    # Generate the URL
    url = blob.generate_signed_url(
        version="v4",
        # Allow PUT requests (uploads)
        method="PUT",
        # URL valid for 15 minutes
        expiration=datetime.timedelta(minutes=15),
        content_type=content_type,
    )

    return {
        "upload_url": url,
        "gcs_path": f"gs://{settings.STORAGE_BUCKET_NAME}/{blob_name}",
        "file_path": blob_name 
    }

def download_file_to_temp(gcs_path: str, local_path: str):
    """
    Downloads a file from GCS to a local path (used by the worker later).
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

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(local_path)
    return local_path

def generate_download_signed_url(gcs_path: str) -> str:
    """
    Generates a secure V4 Signed URL for downloading a file.
    Valid for 15 minutes.
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

    url = blob.generate_signed_url(
        version="v4",
        method="GET",
        expiration=datetime.timedelta(minutes=15),
    )
    
    return url