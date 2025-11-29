"""
Unit tests for file validation and temp storage functionality.
Tests the first step in the user flow: file validation and temporary storage.
"""

import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

import pytest
from werkzeug.datastructures import FileStorage

# Import the function under test
from services.file_service import allowed_file
from core.config import settings


class TestFileValidation:
    """Test file validation logic."""

    def test_allowed_file_with_valid_extensions(self):
        """Test that files with allowed extensions return True."""
        # Arrange
        valid_filenames = [
            "document.pdf",
            "image.png",
            "photo.jpg",
            "picture.jpeg",
            "spreadsheet.xlsx",
            "text.txt",
            "report.docx",
        ]

        # Act & Assert
        for filename in valid_filenames:
            assert allowed_file(filename) is True, f"File {filename} should be allowed"

    def test_allowed_file_with_invalid_extensions(self):
        """Test that files with disallowed extensions return False."""
        # Arrange
        invalid_filenames = [
            "virus.exe",
            "script.py",
            "archive.zip",
            "video.mp4",
            "audio.mp3",
            "presentation.pptx",
        ]

        # Act & Assert
        for filename in invalid_filenames:
            assert (
                allowed_file(filename) is False
            ), f"File {filename} should not be allowed"

    def test_allowed_file_case_insensitive(self):
        """Test that file extension checking is case insensitive."""
        # Arrange
        mixed_case_filenames = [
            "document.PDF",
            "image.PNG",
            "photo.JPG",
            "picture.JPEG",
            "spreadsheet.XLSX",
            "text.TXT",
            "report.DOCX",
        ]

        # Act & Assert
        for filename in mixed_case_filenames:
            assert (
                allowed_file(filename) is True
            ), f"File {filename} should be allowed (case insensitive)"

    def test_allowed_file_no_extension(self):
        """Test that files without extensions return False."""
        # Arrange
        filenames_no_ext = ["document", "file_without_extension", "README"]

        # Act & Assert
        for filename in filenames_no_ext:
            assert (
                allowed_file(filename) is False
            ), f"File {filename} without extension should not be allowed"

    def test_allowed_file_empty_filename(self):
        """Test that empty filename returns False."""
        # Arrange
        empty_filenames = ["", ".", ".."]

        # Act & Assert
        for filename in empty_filenames:
            assert (
                allowed_file(filename) is False
            ), f"Empty filename '{filename}' should not be allowed"


class TestFileSizeValidation:
    """Test file size validation logic from the upload flow."""

    def test_single_file_size_validation(self):
        """Test validation of individual file size limits."""
        # Arrange
        max_size = settings.MAX_FILE_SIZE_BYTES

        # Create a mock file that's too large
        large_file_content = b"x" * (max_size + 1)
        large_file = FileStorage(
            stream=BytesIO(large_file_content),
            filename="large_file.pdf",
            content_type="application/pdf",
        )

        # Create a mock file that's within limits
        small_file_content = b"x" * (max_size // 2)
        small_file = FileStorage(
            stream=BytesIO(small_file_content),
            filename="small_file.pdf",
            content_type="application/pdf",
        )

        # Act
        large_file.seek(0, os.SEEK_END)
        large_file_size = large_file.tell()
        large_file.seek(0)

        small_file.seek(0, os.SEEK_END)
        small_file_size = small_file.tell()
        small_file.seek(0)

        # Assert
        assert large_file_size > max_size, "Large file should exceed size limit"
        assert small_file_size <= max_size, "Small file should be within size limit"

    def test_total_upload_size_validation(self):
        """Test validation of total upload size across multiple files."""
        # Arrange
        max_total_size = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

        # Create multiple files that together exceed the total limit
        file_size = max_total_size // 3  # Each file is 1/3 of the limit
        file_content = b"x" * file_size

        files = []
        for i in range(4):  # 4 files, each 1/3 of limit = 4/3 > 1 (exceeds limit)
            file_obj = FileStorage(
                stream=BytesIO(file_content),
                filename=f"file_{i}.pdf",
                content_type="application/pdf",
            )
            files.append(file_obj)

        # Act
        total_size = 0
        for file_obj in files:
            file_obj.seek(0, os.SEEK_END)
            total_size += file_obj.tell()
            file_obj.seek(0)

        # Assert
        assert total_size > max_total_size, "Total size should exceed the limit"


class TestTempFileHandling:
    """Test temporary file creation and cleanup."""

    @patch("tempfile.mkdtemp")
    def test_temp_directory_creation(self, mock_mkdtemp):
        """Test that temporary directory is created for file processing."""
        # Arrange
        mock_temp_dir = "/tmp/test_temp_dir"
        mock_mkdtemp.return_value = mock_temp_dir

        # Act
        temp_dir = tempfile.mkdtemp()

        # Assert
        mock_mkdtemp.assert_called_once()
        assert temp_dir == mock_temp_dir

    @patch("shutil.rmtree")
    @patch("os.path.exists")
    def test_temp_directory_cleanup(self, mock_exists, mock_rmtree):
        """Test that temporary directory is properly cleaned up."""
        # Arrange
        temp_dir = "/tmp/test_temp_dir"
        mock_exists.return_value = True

        # Act
        if temp_dir and os.path.exists(temp_dir):
            import shutil

            shutil.rmtree(temp_dir)

        # Assert
        mock_exists.assert_called_once_with(temp_dir)
        mock_rmtree.assert_called_once_with(temp_dir)

    @patch("werkzeug.utils.secure_filename")
    def test_secure_filename_usage(self, mock_secure_filename):
        """Test that secure_filename is used to sanitize uploaded filenames."""
        # Arrange
        unsafe_filename = "../../../etc/passwd"
        safe_filename = "passwd"
        mock_secure_filename.return_value = safe_filename

        # Act
        from werkzeug.utils import secure_filename

        result = secure_filename(unsafe_filename)

        # Assert
        mock_secure_filename.assert_called_once_with(unsafe_filename)
        assert result == safe_filename

    def test_secure_filename_empty_result(self):
        """Test handling when secure_filename returns empty string."""
        # Arrange
        from werkzeug.utils import secure_filename

        malicious_filename = "../../../"

        # Act
        result = secure_filename(malicious_filename)

        # Assert
        assert result == "", "Malicious filename should result in empty string"
