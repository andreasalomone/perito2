"""Google Drive service for Live Draft editing.

Handles uploading DOCX to Google Docs and exporting back to DOCX.
Uses Application Default Credentials (ADC) for authentication.

IMPORTANT: Service accounts have 0-byte personal Drive quota (Google policy).
Files MUST be uploaded to a Shared Drive folder to avoid storageQuotaExceeded errors.
"""

import io
import logging
from typing import Optional

from google.auth import default
from google.auth.credentials import Credentials as BaseCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.core.config import settings

logger = logging.getLogger(__name__)


class DriveService:
    """Encapsulates Google Drive API operations for document editing."""

    DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    GDOC_MIME = "application/vnd.google-apps.document"

    def __init__(
        self,
        credentials: Optional[
            BaseCredentials
        ] = None,  # Type hint matches google.oauth2.credentials.Credentials or google.auth.credentials.Credentials
        folder_id: Optional[str] = None,
    ):
        """
        Initialize with ADC or provided credentials.

        Args:
            credentials: Optional credentials, defaults to ADC
            folder_id: Optional Shared Drive folder ID to upload files to.
                       Required for service accounts (they have 0-byte personal quota).
        """
        if credentials is None:
            # PRIORITIZE: User Credentials (OAuth) if configured
            # This is necessary for personal Gmail accounts where Service Accounts have 0 quota.
            if (
                settings.GOOGLE_USER_REFRESH_TOKEN
                and settings.GOOGLE_CLIENT_ID
                and settings.GOOGLE_CLIENT_SECRET
            ):
                logger.info("Using OAuth User Credentials for Drive Service")
                credentials = OAuthCredentials(
                    None,  # Access token (will be refreshed)
                    refresh_token=settings.GOOGLE_USER_REFRESH_TOKEN,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=settings.GOOGLE_CLIENT_ID,
                    client_secret=settings.GOOGLE_CLIENT_SECRET,
                )
            else:
                # FALLBACK: Service Account (ADC)
                # Only works if target folder is in a Shared Drive (or SA has quota)
                logger.info("Using Service Account (ADC) for Drive Service")
                credentials, _ = default(
                    scopes=["https://www.googleapis.com/auth/drive"]
                )

        self.service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )
        self.folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID

    def create_editable_draft(self, docx_stream: io.BytesIO, filename: str) -> dict:
        """
        Upload DOCX to Google Drive as a Google Doc with public edit access.

        Args:
            docx_stream: BytesIO containing the DOCX file
            filename: Display name for the Google Doc

        Returns:
            dict with 'file_id' and 'url' keys

        Raises:
            ValueError: If no folder_id is configured (required for service accounts)
        """
        # Reset stream position
        docx_stream.seek(0)

        # Build file metadata
        # MUST use a folder owned by a user (or Shared Drive) to avoid 0-byte service account quota
        file_metadata: dict = {
            "name": filename,
            "mimeType": self.GDOC_MIME,
        }

        # Add parent folder (Required for Shared Drive OR Shared Folder workaround)
        if self.folder_id:
            file_metadata["parents"] = [self.folder_id]
            logger.info(f"Uploading to drive folder: {self.folder_id}")
        else:
            logger.warning(
                "No GOOGLE_DRIVE_FOLDER_ID configured! "
                "Service accounts have 0-byte personal quota and will fail."
            )

        media = MediaIoBaseUpload(docx_stream, mimetype=self.DOCX_MIME, resumable=True)

        # Use supportsAllDrives=True for Shared Drive compatibility
        file = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )

        file_id = file["id"]

        # Set permissions: anyone with link can edit
        # supportsAllDrives=True is required for Shared Drive files
        self.service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "writer"},
            fields="id",
            supportsAllDrives=True,
        ).execute()

        logger.info(f"Created Google Doc {file_id} with public edit access")

        return {"file_id": file_id, "url": file["webViewLink"]}

    def export_as_docx(self, file_id: str) -> bytes:
        """
        Export a Google Doc as DOCX format.

        Args:
            file_id: Google Drive file ID

        Returns:
            bytes containing the DOCX file content
        """
        request = self.service.files().export_media(
            fileId=file_id, mimeType=self.DOCX_MIME
        )

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        buffer.seek(0)
        logger.info(
            f"Exported Google Doc {file_id} as DOCX ({buffer.getbuffer().nbytes} bytes)"
        )
        return buffer.getvalue()

    def delete_file(self, file_id: str) -> None:
        """
        Delete a file from Google Drive.

        Args:
            file_id: Google Drive file ID
        """
        # supportsAllDrives=True required for Shared Drive files
        self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        logger.info(f"Deleted Google Doc {file_id}")

    def export_and_delete(self, file_id: str) -> bytes:
        """
        Export a Google Doc as DOCX and then delete the temporary file.

        Args:
            file_id: Google Drive file ID

        Returns:
            bytes containing the DOCX file content
        """
        docx_bytes = self.export_as_docx(file_id)
        self.delete_file(file_id)
        return docx_bytes


def get_drive_service() -> DriveService:
    """Factory function for dependency injection."""
    return DriveService()
