"""Google Drive service for Live Draft editing.

Handles uploading DOCX to Google Docs and exporting back to DOCX.
Uses Application Default Credentials (ADC) for authentication.
"""

import io
import logging
from typing import Optional

from google.auth import default
from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

logger = logging.getLogger(__name__)


class DriveService:
    """Encapsulates Google Drive API operations for document editing."""

    DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    GDOC_MIME = "application/vnd.google-apps.document"

    def __init__(self, credentials: Optional[Credentials] = None):
        """Initialize with ADC or provided credentials."""
        if credentials is None:
            credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
        self.service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )

    def create_editable_draft(self, docx_stream: io.BytesIO, filename: str) -> dict:
        """
        Upload DOCX to Google Drive as a Google Doc with public edit access.

        Args:
            docx_stream: BytesIO containing the DOCX file
            filename: Display name for the Google Doc

        Returns:
            dict with 'file_id' and 'url' keys
        """
        # Reset stream position
        docx_stream.seek(0)

        # Upload with conversion to Google Docs format
        file_metadata = {
            "name": filename,
            "mimeType": self.GDOC_MIME,
        }
        media = MediaIoBaseUpload(docx_stream, mimetype=self.DOCX_MIME, resumable=True)

        file = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )

        file_id = file["id"]

        # Set permissions: anyone with link can edit
        self.service.permissions().create(
            fileId=file_id, body={"type": "anyone", "role": "writer"}, fields="id"
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
        self.service.files().delete(fileId=file_id).execute()
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
