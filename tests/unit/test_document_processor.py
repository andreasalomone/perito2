"""
Unit tests for document processor functionality.
Tests the document processing step in the user flow: file type detection and content preparation.
"""

import io
import os
import tempfile
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
from PIL import Image

# Import the functions under test
import document_processor
from document_processor import (
    extract_text_from_docx,
    extract_text_from_txt,
    extract_text_from_xlsx,
    handle_extraction_errors,
    prepare_image_for_llm,
    prepare_pdf_for_llm,
    process_uploaded_file,
)


class TestFileTypeDetection:
    """Test file type detection and routing to appropriate processors."""

    def test_process_uploaded_file_pdf(self):
        """Test that PDF files are routed to PDF processor."""
        # Arrange
        pdf_path = "/tmp/test.pdf"

        with patch("document_processor.prepare_pdf_for_llm") as mock_pdf_processor:
            mock_pdf_processor.return_value = {
                "type": "vision",
                "path": pdf_path,
                "mime_type": "application/pdf",
                "filename": "test.pdf",
            }

            # Act
            result = process_uploaded_file(pdf_path, upload_folder="/tmp")

            # Assert
            mock_pdf_processor.assert_called_once_with(pdf_path)
            assert result["type"] == "vision"
            assert result["filename"] == "test.pdf"

    def test_process_uploaded_file_image_types(self):
        """Test that image files are routed to image processor."""
        # Arrange
        image_extensions = [".png", ".jpg", ".jpeg", ".webp", ".gif"]

        for ext in image_extensions:
            image_path = f"/tmp/test{ext}"

            with patch(
                "document_processor.prepare_image_for_llm"
            ) as mock_image_processor:
                mock_image_processor.return_value = {
                    "type": "vision",
                    "path": image_path,
                    "mime_type": f"image/{ext[1:]}",
                    "filename": f"test{ext}",
                }

                # Act
                result = process_uploaded_file(image_path, upload_folder="/tmp")

                # Assert
                mock_image_processor.assert_called_once_with(image_path)
                assert result["type"] == "vision"
                assert result["filename"] == f"test{ext}"

    def test_process_uploaded_file_docx(self):
        """Test that DOCX files are routed to DOCX processor."""
        # Arrange
        docx_path = "/tmp/test.docx"

        with patch("document_processor.extract_text_from_docx") as mock_docx_processor:
            mock_docx_processor.return_value = {
                "type": "text",
                "content": "Sample DOCX content",
                "filename": "test.docx",
            }

            # Act
            result = process_uploaded_file(docx_path, upload_folder="/tmp")

            # Assert
            mock_docx_processor.assert_called_once_with(docx_path)
            assert result["type"] == "text"
            assert result["content"] == "Sample DOCX content"

    def test_process_uploaded_file_xlsx(self):
        """Test that XLSX files are routed to XLSX processor."""
        # Arrange
        xlsx_path = "/tmp/test.xlsx"

        with patch("document_processor.extract_text_from_xlsx") as mock_xlsx_processor:
            mock_xlsx_processor.return_value = {
                "type": "text",
                "content": "--- Sheet: Sheet1 ---\nData1,Data2\n",
                "filename": "test.xlsx",
            }

            # Act
            result = process_uploaded_file(xlsx_path, upload_folder="/tmp")

            # Assert
            mock_xlsx_processor.assert_called_once_with(xlsx_path)
            assert result["type"] == "text"
            assert "Sheet1" in result["content"]

    def test_process_uploaded_file_txt(self):
        """Test that TXT files are routed to TXT processor."""
        # Arrange
        txt_path = "/tmp/test.txt"

        with patch("document_processor.extract_text_from_txt") as mock_txt_processor:
            mock_txt_processor.return_value = {
                "type": "text",
                "content": "Sample text content",
                "filename": "test.txt",
            }

            # Act
            result = process_uploaded_file(txt_path, upload_folder="/tmp")

            # Assert
            mock_txt_processor.assert_called_once_with(txt_path)
            assert result["type"] == "text"
            assert result["content"] == "Sample text content"

    def test_process_uploaded_file_unsupported_extension(self):
        """Test handling of unsupported file extensions."""
        # Arrange
        unsupported_path = "/tmp/test.exe"

        # Act
        result = process_uploaded_file(unsupported_path, upload_folder="/tmp")

        # Assert
        assert result["type"] == "unsupported"
        assert result["filename"] == "test.exe"
        assert "Unsupported file type" in result["message"]


class TestPDFProcessor:
    """Test PDF file processing for LLM vision input."""

    @patch("fitz.open")
    def test_prepare_pdf_for_llm_valid_pdf(self, mock_fitz_open):
        """Test successful PDF preparation for LLM."""
        # Arrange
        pdf_path = "/tmp/test.pdf"
        mock_doc = Mock()
        mock_fitz_open.return_value = mock_doc

        # Act
        result = prepare_pdf_for_llm(pdf_path)

        # Assert
        mock_fitz_open.assert_called_once_with(pdf_path)
        mock_doc.close.assert_called_once()
        assert result["type"] == "vision"
        assert result["path"] == pdf_path
        assert result["mime_type"] == "application/pdf"
        assert result["filename"] == "test.pdf"

    @patch("fitz.open")
    def test_prepare_pdf_for_llm_corrupted_pdf(self, mock_fitz_open):
        """Test handling of corrupted PDF files."""
        # Arrange
        pdf_path = "/tmp/corrupted.pdf"
        mock_fitz_open.side_effect = Exception("PDF is corrupted")

        # Act
        result = prepare_pdf_for_llm(pdf_path)

        # Assert
        assert result["type"] == "error"
        assert result["filename"] == "corrupted.pdf"
        assert "error" in result["message"].lower()


class TestImageProcessor:
    """Test image file processing for LLM vision input."""

    @patch("PIL.Image.open")
    @patch("mimetypes.guess_type")
    def test_prepare_image_for_llm_valid_image(self, mock_guess_type, mock_image_open):
        """Test successful image preparation for LLM."""
        # Arrange
        image_path = "/tmp/test.png"
        mock_img = Mock()
        mock_image_open.return_value = mock_img
        mock_guess_type.return_value = ("image/png", None)

        # Act
        result = prepare_image_for_llm(image_path)

        # Assert
        mock_image_open.assert_called_once_with(image_path)
        mock_img.close.assert_called_once()
        assert result["type"] == "vision"
        assert result["path"] == image_path
        assert result["mime_type"] == "image/png"
        assert result["filename"] == "test.png"

    @patch("PIL.Image.open")
    def test_prepare_image_for_llm_corrupted_image(self, mock_image_open):
        """Test handling of corrupted image files."""
        # Arrange
        image_path = "/tmp/corrupted.png"
        mock_image_open.side_effect = Image.UnidentifiedImageError(
            "Cannot identify image"
        )

        # Act
        result = prepare_image_for_llm(image_path)

        # Assert
        assert result["type"] == "error"
        assert result["filename"] == "corrupted.png"
        assert "Cannot identify image file" in result["message"]

    @patch("PIL.Image.open")
    @patch("mimetypes.guess_type")
    def test_prepare_image_for_llm_unknown_mime_type(
        self, mock_guess_type, mock_image_open
    ):
        """Test handling when MIME type cannot be determined."""
        # Arrange
        image_path = "/tmp/test.unknown"
        mock_img = Mock()
        mock_image_open.return_value = mock_img
        mock_guess_type.return_value = (None, None)

        # Act
        result = prepare_image_for_llm(image_path)

        # Assert
        assert result["type"] == "vision"
        assert result["mime_type"] == "application/octet-stream"


class TestTextExtractors:
    """Test text extraction from various document types."""

    @patch("document_processor.DocxDocument")
    def test_extract_text_from_docx_success(self, mock_document):
        """Test successful text extraction from DOCX."""
        # Arrange
        docx_path = "/tmp/test.docx"
        mock_doc = Mock()
        mock_paragraph1 = Mock()
        mock_paragraph1.text = "First paragraph"
        mock_paragraph2 = Mock()
        mock_paragraph2.text = "Second paragraph"
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
        mock_document.return_value = mock_doc

        # Act
        result = extract_text_from_docx(docx_path)

        # Assert
        mock_document.assert_called_once_with(docx_path)
        assert result["type"] == "text"
        assert result["content"] == "First paragraph\nSecond paragraph"
        assert result["filename"] == "test.docx"

    @patch("openpyxl.load_workbook")
    def test_extract_text_from_xlsx_success(self, mock_load_workbook):
        """Test successful text extraction from XLSX."""
        # Arrange
        xlsx_path = "/tmp/test.xlsx"
        mock_workbook = Mock()
        mock_workbook.sheetnames = ["Sheet1", "Sheet2"]

        # Mock Sheet1
        mock_sheet1 = Mock()
        mock_cell1 = Mock()
        mock_cell1.value = "A1"
        mock_cell2 = Mock()
        mock_cell2.value = "B1"
        mock_row1 = [mock_cell1, mock_cell2]
        mock_sheet1.iter_rows.return_value = [mock_row1]

        # Mock Sheet2
        mock_sheet2 = Mock()
        mock_cell3 = Mock()
        mock_cell3.value = "A2"
        mock_cell4 = Mock()
        mock_cell4.value = None
        mock_row2 = [mock_cell3, mock_cell4]
        mock_sheet2.iter_rows.return_value = [mock_row2]

        mock_workbook.__getitem__ = Mock(
            side_effect=lambda x: mock_sheet1 if x == "Sheet1" else mock_sheet2
        )
        mock_load_workbook.return_value = mock_workbook

        # Act
        result = extract_text_from_xlsx(xlsx_path)

        # Assert
        mock_load_workbook.assert_called_once_with(xlsx_path)
        mock_workbook.close.assert_called_once()
        assert result["type"] == "text"
        assert "--- Sheet: Sheet1 ---" in result["content"]
        assert "--- Sheet: Sheet2 ---" in result["content"]
        assert "A1,B1" in result["content"]
        assert "A2," in result["content"]  # None value becomes empty string

    def test_extract_text_from_txt_success(self):
        """Test successful text extraction from TXT."""
        # Arrange
        txt_path = "/tmp/test.txt"
        txt_content = "This is a test text file.\nWith multiple lines."

        with patch("builtins.open", mock_open(read_data=txt_content)):
            # Act
            result = extract_text_from_txt(txt_path)

            # Assert
            assert result["type"] == "text"
            assert result["content"] == txt_content
            assert result["filename"] == "test.txt"


class TestErrorHandling:
    """Test error handling decorator and exception scenarios."""

    def test_handle_extraction_errors_file_not_found(self):
        """Test error handling when file is not found."""

        # Arrange
        @handle_extraction_errors()
        def mock_processor(file_path):
            raise FileNotFoundError("File not found")

        # Act
        result = mock_processor("/nonexistent/file.pdf")

        # Assert
        assert result["type"] == "error"
        assert "File not found" in result["message"]

    def test_handle_extraction_errors_with_custom_default(self):
        """Test error handling with custom default return value."""
        # Arrange
        custom_default = {"type": "custom_error", "message": "Custom error"}

        @handle_extraction_errors(custom_default)
        def mock_processor(file_path):
            raise Exception("Some error")

        # Act
        result = mock_processor("/some/file.pdf")

        # Assert
        assert result["type"] == "error"
        assert result["filename"] == "file.pdf"
        assert "Some error" in result["message"]

    def test_handle_extraction_errors_unexpected_exception(self):
        """Test error handling for unexpected exceptions."""

        # Arrange
        @handle_extraction_errors()
        def mock_processor(file_path):
            raise ValueError("Unexpected error")

        # Act
        result = mock_processor("/some/file.pdf")

        # Assert
        assert result["type"] == "error"
        assert "Unexpected error" in result["message"]

    @patch("openpyxl.load_workbook")
    def test_extract_text_from_xlsx_invalid_file(self, mock_load_workbook):
        """Test handling of invalid XLSX files."""
        # Arrange
        xlsx_path = "/tmp/invalid.xlsx"
        mock_load_workbook.side_effect = Exception("Invalid Excel file")

        # Act
        result = extract_text_from_xlsx(xlsx_path)

        # Assert
        assert result["type"] == "error"
        assert result["filename"] == "invalid.xlsx"
        assert "error" in result["message"].lower()


class TestFilenameHandling:
    """Test filename extraction and handling."""

    def test_filename_extraction_from_path(self):
        """Test that filenames are correctly extracted from full paths."""
        # Arrange
        test_cases = [
            ("/tmp/test.pdf", "test.pdf"),
            ("/home/user/documents/report.docx", "report.docx"),
            (
                os.path.normpath("C:/Users/test/file.xlsx"),
                "file.xlsx",
            ),  # Use forward slashes and normalize
            ("simple_file.txt", "simple_file.txt"),
        ]

        for file_path, expected_filename in test_cases:
            # Act
            actual_filename = os.path.basename(file_path)

            # Assert
            assert actual_filename == expected_filename, f"Failed for path: {file_path}"

    def test_filename_in_result_when_processor_fails(self):
        """Test that filename is included in result even when processing fails."""
        # Arrange
        file_path = "/tmp/test.pdf"

        with patch("fitz.open", side_effect=Exception("Processing failed")):
            # Act
            result = prepare_pdf_for_llm(file_path)

            # Assert
            assert "filename" in result
            assert result["filename"] == "test.pdf"
