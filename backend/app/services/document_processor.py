import base64
import binascii
import datetime
import functools
import io
import logging
import mimetypes
import os
import re
import string
import uuid
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Set, TypeVar

import fitz  # PyMuPDF
import mailparser
from charset_normalizer import from_bytes
from PIL import Image

# --- Security Constants (External Audit) ---
MAX_RECURSION_DEPTH = 3
MAX_EML_ATTACHMENTS = 20  # Prevent inode exhaustion attacks
MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_B64_STRING_LENGTH = int(
    MAX_ATTACHMENT_SIZE_BYTES * 1.35
)  # ~33.75 MB (b64 overhead)
TINY_IMAGE_THRESHOLD_BYTES = 5 * 1024  # 5 KB
TINY_IMAGE_DIMENSION_PX = 100

# --- Image Extension Constants (DRY: avoid duplicating literals) ---
EXT_JPG = ".jpg"
EXT_JPEG = ".jpeg"
EXT_PNG = ".png"
EXT_WEBP = ".webp"
EXT_GIF = ".gif"
IMAGE_EXTENSIONS_FOR_LLM: Set[str] = {EXT_PNG, EXT_JPG, EXT_JPEG, EXT_WEBP, EXT_GIF}
TINY_IMAGE_EXTENSIONS: Set[str] = {EXT_PNG, EXT_JPG, EXT_JPEG, EXT_GIF, EXT_WEBP}
EXCLUDED_EXTENSIONS: Set[str] = {
    ".gif",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".exe",
    ".bin",
}


# --- HTML Stripper (stdlib - safer than regex) ---
class _MLStripper(HTMLParser):
    """Safe HTML tag stripper using stdlib (avoids regex parsing HTML)."""

    def __init__(self) -> None:
        super().__init__()
        self._text = io.StringIO()
        self.convert_charrefs = True

    def handle_data(self, d: str) -> None:
        self._text.write(d)

    def get_data(self) -> str:
        return self._text.getvalue()


def _strip_html(html_content: str) -> str:
    """Removes HTML tags using a proper parser."""
    try:
        s = _MLStripper()
        s.feed(html_content)
        return s.get_data().strip()
    except Exception:
        # Fallback if parser chokes
        return re.sub(r"<[^>]+>", "", html_content).strip()


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to prevent path traversal and remove dangerous characters.
    Keeps alphanumeric, dots, dashes, and underscores.
    """
    # Remove path components
    filename = os.path.basename(filename)
    # Replace anything that isn't alphanumeric, ., -, or _
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return filename


def sanitize_text_content(content: str) -> str:
    """
    Sanitizes extracted text content for safe storage in PostgreSQL JSONB.

    Removes NULL bytes (\x00) which cause:
    - asyncpg.exceptions.UntranslatableCharacterError: \u0000 cannot be converted to text

    These NULL bytes commonly appear in:
    - PDF text extraction (embedded fonts, malformed documents)
    - Binary data accidentally decoded as text
    - EML attachments with binary content
    """
    return content.replace("\x00", "") if content else content


logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def handle_extraction_errors() -> Callable[[F], F]:
    """Decorator to handle common exceptions during file processing."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(file_path: str, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(file_path, *args, **kwargs)
            except (
                ValueError,
                fitz.FileDataError,
                zipfile.BadZipFile,
            ) as e:
                # Domain errors: Return error dict for user visibility
                logger.warning(f"Domain error processing {file_path}: {e}")
                return [
                    {
                        "type": "error",
                        "filename": os.path.basename(file_path),
                        "message": str(e),
                    }
                ]
            except MemoryError as e:
                # CRITICAL: OOM should propagate to monitoring systems
                logger.critical(f"CRITICAL: Out of memory processing {file_path}: {e}")
                raise
            except OSError as e:
                # CRITICAL: Disk full or I/O errors should propagate
                # ENOSPC (28) = No space left on device
                # EDQUOT (122) = Disk quota exceeded
                if hasattr(e, "errno") and e.errno in [28, 122]:
                    logger.critical(f"CRITICAL: Disk full processing {file_path}: {e}")
                    raise
                # Other OS errors might be recoverable (permissions, etc) but often indicate system issues.
                # For safety in this refactor, we will RAISE them to be caught by the caller
                # unless we are sure they are user errors.
                logger.error(f"OS error processing {file_path}: {e}", exc_info=True)
                raise
            except Exception as e:
                # Unexpected system errors (Bug, etc): RAISE them.
                logger.error(
                    f"Critical failure processing {file_path}: {e}", exc_info=True
                )
                raise

        return wrapper  # type: ignore

    return decorator


# --- Standardized Extractors (All return List[Dict]) ---


@handle_extraction_errors()
def prepare_pdf_for_llm(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Prepares a PDF for LLM processing.

    PDFs are sent directly as vision assets. The LLM (Gemini) handles
    text extraction via its native OCR, eliminating redundant PyMuPDF parsing.
    """
    return [
        {
            "type": "vision",
            "path": pdf_path,
            "mime_type": "application/pdf",
            "filename": sanitize_filename(os.path.basename(pdf_path)),
        }
    ]


@handle_extraction_errors()
def prepare_image_for_llm(image_path: str) -> List[Dict[str, Any]]:
    pil_format = None
    # Validate image and get format (JPEG, PNG, etc.)
    with Image.open(image_path) as img:
        img.verify()
        pil_format = img.format

    mime_type, _ = mimetypes.guess_type(image_path)

    # Robust Fallback: Use PIL format if system mimetypes fails
    if (not mime_type or not mime_type.startswith("image/")) and pil_format:
        fmt = pil_format.upper()
        if fmt == "JPEG":
            mime_type = "image/jpeg"
        elif fmt == "PNG":
            mime_type = "image/png"
        elif fmt == "WEBP":
            mime_type = "image/webp"
        elif fmt == "GIF":
            mime_type = "image/gif"

    # Second Fallback: File extension (if PIL failed or format unknown)
    if not mime_type:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in [EXT_JPG, EXT_JPEG]:
            mime_type = "image/jpeg"
        elif ext == ".png":
            mime_type = "image/png"
        elif ext == ".webp":
            mime_type = "image/webp"

    if not mime_type or not mime_type.startswith("image/"):
        logger.warning(
            f"Could not determine mime type for {image_path}, defaulting to application/octet-stream"
        )
        mime_type = "application/octet-stream"

    return [
        {
            "type": "vision",
            "path": image_path,
            "mime_type": mime_type,
            "filename": sanitize_filename(os.path.basename(image_path)),
        }
    ]


@handle_extraction_errors()
def extract_text_from_docx(docx_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text from DOCX using streaming XML parsing (SAX-like).
    This avoids loading the entire document object model into memory,
    fixing the 'Major' memory vulnerability identified in the audit.
    """
    text_content = []
    try:
        with zipfile.ZipFile(docx_path) as zf:
            if "word/document.xml" not in zf.namelist():
                raise ValueError("Invalid DOCX: Missing word/document.xml")

            with zf.open("word/document.xml") as f:
                # iterparse is a streaming parser
                context = ET.iterparse(f, events=("end",))
                for _event, elem in context:
                    # w:t is the tag for text in Word XML
                    if elem.tag.endswith("}t") and elem.text:
                        text_content.append(elem.text)
                    # Clean up element to free memory
                    elem.clear()

        full_text = "\n".join(text_content)

    except Exception as e:
        logger.warning(
            f"Fast extraction failed: {e}. Falling back to standard method if needed, or failing."
        )
        raise e

    return [
        {
            "type": "text",
            "content": sanitize_text_content(full_text),
            "filename": sanitize_filename(os.path.basename(docx_path)),
        }
    ]


# --- Hard Limits for XLSX Stability ---
MAX_SHARED_STRINGS_COUNT = 50_000  # Max unique strings to hold in RAM
MAX_XLSX_SHEET_ROWS = 10_000
MAX_XLSX_TEXT_OUTPUT = 5 * 1024 * 1024  # 5 MB
MAX_COL_WIDTH = (
    50  # Safety cap on columns to prevent sparse vector attacks (e.g., cell XFD1)
)
EXCEL_EPOCH = datetime.datetime(1899, 12, 30)


def _excel_date_to_string(serial: float) -> str:
    """
    Converts Excel serial date format (float) to ISO string.
    Excel treats 1900 as a leap year (bug), but for modern dates this suffices.
    """
    try:
        delta = datetime.timedelta(days=serial)
        return (EXCEL_EPOCH + delta).date().isoformat()
    except Exception:
        return str(serial)


def _col_to_int(col_label: str) -> int:
    """
    Converts Excel column letter to 0-based index.
    A -> 0, Z -> 25, AA -> 26, XFD -> 16383
    Handles both uppercase and lowercase input.
    """
    num = 0
    for c in col_label.upper():
        if "A" <= c <= "Z":
            num = num * 26 + (ord(c) - ord("A") + 1)
    return num - 1


def _extract_col_from_ref(r_attr: str) -> str:
    """Extracts column letter from cell reference (e.g., 'AA12' -> 'AA').
    Handles both uppercase and lowercase input.
    """
    match = re.match(r"([A-Za-z]+)", r_attr)
    return match[1].upper() if match else "A"


def _parse_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    """
    Parses the sharedStrings.xml file with a hard memory cap.
    Returns a list of strings. Raises MemoryError if limit exceeded.

    This is the most memory-intensive part of XLSX parsing.
    By capping this, we prevent "SharedStrings Explosion" attacks.
    """
    shared_strings: List[str] = []

    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    with zf.open("xl/sharedStrings.xml") as f:
        # events=("end",) triggers when a closing tag is found
        context = ET.iterparse(f, events=("end",))
        for _, elem in context:
            # Excel stores shared strings in <si><t>value</t></si>
            if elem.tag.endswith("}t") and elem.text:
                shared_strings.append(elem.text)

                # GUARD: Memory Explosion Protection
                if len(shared_strings) > MAX_SHARED_STRINGS_COUNT:
                    raise MemoryError(
                        f"XLSX contains too many unique strings (>{MAX_SHARED_STRINGS_COUNT:,}). "
                        "Processing aborted to protect system stability."
                    )

            # Vital: Clear element to free memory
            if elem.tag.endswith("}si"):
                elem.clear()

    return shared_strings


def _get_cell_value(
    elem: ET.Element, cell_type: str | None, shared_strings: List[str]
) -> str:
    """Extract the value from a cell element based on its type."""
    v_tag = elem.find("{*}v")  # Namespace wildcard

    if v_tag is not None and v_tag.text:
        raw_val = v_tag.text

        if cell_type == "s":
            return _resolve_shared_string(raw_val, shared_strings)
        if cell_type == "b":
            return "TRUE" if raw_val == "1" else "FALSE"
        return raw_val if cell_type == "str" else _parse_numeric_value(raw_val)
    # Handle Inline Strings <is><t>val</t></is>
    is_tag = elem.find("{*}is")
    if is_tag is not None:
        t_tag = is_tag.find("{*}t")
        if t_tag is not None and t_tag.text:
            return t_tag.text

    return ""


def _resolve_shared_string(raw_val: str, shared_strings: List[str]) -> str:
    """Resolve a shared string index to its value."""
    try:
        idx = int(raw_val)
        return shared_strings[idx] if 0 <= idx < len(shared_strings) else "[ERR:REF]"
    except ValueError:
        return "[ERR:IDX]"


def _parse_numeric_value(raw_val: str) -> str:
    """Parse a numeric cell value.

    NOTE: Date detection via heuristic (checking if value is in range 20000-60000)
    was removed because it caused false positives for numeric IDs, prices, and
    quantities. Excel dates will appear as serial numbers. For proper date handling,
    the cell's numFmtId from styles.xml would need to be parsed.
    """
    try:
        f_val = float(raw_val)
        # Return integers without decimal, floats with 2 decimal places
        return str(int(f_val)) if f_val == int(f_val) else f"{f_val:.2f}"
    except ValueError:
        return raw_val


def _finalize_row_to_markdown(
    row_data: Dict[int, str], table_width: int, is_header: bool
) -> str:
    """Convert a sparse row dict to a markdown table row."""
    dense_row = [row_data.get(i, "") or "-" for i in range(table_width)]
    line = "| " + " | ".join(dense_row) + " |\n"

    if is_header:
        separator = "| " + " | ".join(["---"] * table_width) + " |\n"
        line += separator

    return line


def _get_column_index(elem: ET.Element, fallback: int) -> int:
    """Extract column index from cell element's 'r' attribute."""
    if r_attr := elem.get("r"):
        col_letter = _extract_col_from_ref(r_attr)
        return _col_to_int(col_letter)
    return fallback


def _process_xlsx_sheet(
    zf: zipfile.ZipFile,
    sheet_file: str,
    shared_strings: List[str],
    output_parts: List[str],
    total_chars: int,
) -> tuple[int, bool]:
    """
    Process a single XLSX sheet with streaming XML parsing.

    Returns: (updated_total_chars, was_truncated)
    """
    row_data: Dict[int, str] = {}
    current_row_index = 0
    table_width = 0
    is_first_valid_row = True

    with zf.open(sheet_file) as f:
        context = ET.iterparse(f, events=("end",))

        for _, elem in context:
            if elem.tag.endswith("}row"):
                result = _handle_row_end(
                    row_data,
                    current_row_index,
                    table_width,
                    is_first_valid_row,
                    output_parts,
                    total_chars,
                )
                (
                    current_row_index,
                    table_width,
                    is_first_valid_row,
                    total_chars,
                    truncated,
                ) = result
                row_data.clear()
                elem.clear()

                if truncated:
                    return total_chars, True
                continue

            if elem.tag.endswith("}c"):
                _handle_cell(elem, row_data, shared_strings)
                elem.clear()

    return total_chars, False


def _handle_row_end(
    row_data: Dict[int, str],
    current_row_index: int,
    table_width: int,
    is_first_valid_row: bool,
    output_parts: List[str],
    total_chars: int,
) -> tuple[int, int, bool, int, bool]:
    """
    Handle end of a row element.

    Returns: (new_row_index, table_width, is_first_valid_row, total_chars, truncated)
    """
    current_row_index += 1

    if current_row_index > MAX_XLSX_SHEET_ROWS:
        output_parts.append(f"\n*[TRUNCATED: > {MAX_XLSX_SHEET_ROWS:,} rows]*\n")
        return current_row_index, table_width, is_first_valid_row, total_chars, True

    if not row_data:
        return current_row_index, table_width, is_first_valid_row, total_chars, False

    if is_first_valid_row:
        table_width = min(max(row_data.keys()) + 1, MAX_COL_WIDTH)

    line = _finalize_row_to_markdown(row_data, table_width, is_first_valid_row)
    if is_first_valid_row:
        is_first_valid_row = False

    if total_chars + len(line) > MAX_XLSX_TEXT_OUTPUT:
        output_parts.append("\n*[TRUNCATED: Output Size Limit]*\n")
        return current_row_index, table_width, is_first_valid_row, total_chars, True

    output_parts.append(line)
    total_chars += len(line)
    return current_row_index, table_width, is_first_valid_row, total_chars, False


def _handle_cell(
    elem: ET.Element, row_data: Dict[int, str], shared_strings: List[str]
) -> None:
    """Process a cell element and add its value to row_data."""
    col_idx = _get_column_index(elem, len(row_data))

    if col_idx >= MAX_COL_WIDTH:
        return

    cell_type = elem.get("t")
    cell_val = _get_cell_value(elem, cell_type, shared_strings)
    if clean_val := cell_val.strip().replace("|", "/"):
        row_data[col_idx] = clean_val


@handle_extraction_errors()
def extract_text_from_xlsx(xlsx_path: str) -> List[Dict[str, Any]]:
    """
    High-Performance, Low-Memory XLSX Extractor (Sparse-Safe).

    Features:
    - Streaming XML parsing (iterparse) - O(1) memory
    - Sparse row handling - preserves column alignment
    - SharedStrings cap: 50,000 unique strings max
    - Row limit: 10,000 per sheet
    - Column limit: 50 columns max (prevents XFD attacks)
    - Output limit: 5MB text

    Output: Markdown tables for LLM comprehension.
    """
    # Validity check - ValueError will be caught by @handle_extraction_errors
    if not zipfile.is_zipfile(xlsx_path):
        raise ValueError("File is not a valid zip/xlsx archive")

    # Core extraction with user-friendly error handling
    try:
        return _extract_xlsx_content(xlsx_path)
    except zipfile.BadZipFile:
        # User-friendly message instead of technical exception string
        logger.error(f"Bad zip file: {xlsx_path}")
        return [_make_error_result(xlsx_path, "Corrupted or invalid XLSX file")]
    except MemoryError:
        # Let MemoryError propagate to decorator for CRITICAL logging
        raise
    except Exception as e:
        # User-friendly wrapper for unexpected errors
        logger.error(f"Error extracting XLSX {xlsx_path}: {e}", exc_info=True)
        return [_make_error_result(xlsx_path, f"Extraction failed: {str(e)}")]


def _extract_xlsx_content(xlsx_path: str) -> List[Dict[str, Any]]:
    """Core XLSX extraction logic."""
    output_parts: List[str] = []
    total_chars = 0

    with zipfile.ZipFile(xlsx_path, "r") as zf:
        shared_strings_result = _load_shared_strings_safe(zf, xlsx_path)
        # Check if we got an error result (MemoryError during parsing)
        if shared_strings_result is None:
            return [
                _make_error_result(
                    xlsx_path, "Memory limit exceeded parsing shared strings"
                )
            ]
        shared_strings = shared_strings_result

        sheet_files = sorted(
            [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")]
        )

        if not sheet_files:
            return [_make_error_result(xlsx_path, "No worksheets found in Excel file.")]

        for sheet_file in sheet_files:
            sheet_name = os.path.basename(sheet_file).replace(".xml", "")
            output_parts.append(f"\n## Sheet: {sheet_name}\n\n")

            total_chars, truncated = _process_xlsx_sheet(
                zf, sheet_file, shared_strings, output_parts, total_chars  # type: ignore[arg-type]
            )
            if truncated:
                break

    return [
        {
            "type": "text",
            "content": sanitize_text_content("".join(output_parts)),
            "filename": sanitize_filename(os.path.basename(xlsx_path)),
        }
    ]


def _load_shared_strings_safe(zf: zipfile.ZipFile, xlsx_path: str) -> List[str] | None:
    """Load shared strings with memory protection. Returns None on MemoryError."""
    try:
        return _parse_shared_strings(zf)
    except MemoryError as e:
        logger.warning(f"Rejected XLSX {xlsx_path}: {e}")
        return None


def _make_error_result(xlsx_path: str, message: str) -> Dict[str, Any]:
    """Create a standardized error result dictionary."""
    return {
        "type": "error",
        "filename": sanitize_filename(os.path.basename(xlsx_path)),
        "message": message,
    }


@handle_extraction_errors()
def extract_text_from_txt(txt_path: str) -> List[Dict[str, Any]]:
    # Prevent OOM on maliciously large text files
    MAX_TXT_SIZE = 50 * 1024 * 1024  # 50MB (Transcript-friendly)
    file_size = os.path.getsize(txt_path)
    if file_size > MAX_TXT_SIZE:
        logger.warning(
            f"Text file {txt_path} is too large ({file_size} bytes). Skipping."
        )
        return [
            {
                "type": "error",
                "filename": sanitize_filename(os.path.basename(txt_path)),
                "message": f"File too large ({file_size:,} bytes, max {MAX_TXT_SIZE:,} bytes)",
            }
        ]

    # Read raw bytes and detect encoding using charset-normalizer.
    # We use a context manager to ensure the file is closed immediately after reading.
    with open(txt_path, "rb") as f:
        raw_bytes = f.read()

    # Use charset-normalizer for intelligent detection
    detection_result = from_bytes(raw_bytes)
    best_match = detection_result.best()

    # CRITICAL: We clear raw_bytes as soon as we have the string to free memory.
    # For a 50MB file, this frees ~50MB RAM immediately.

    if best_match is not None:
        content = str(best_match)
        detected_encoding = best_match.encoding
        logger.debug(f"Detected encoding '{detected_encoding}' for {txt_path}")
        # Explicitly delete raw_bytes to help GC
        del raw_bytes
    else:
        # Fallback: try common encodings manually if detection fails
        # Order: BOM-aware first, then common Western encodings
        content = None
        for encoding in ("utf-8-sig", "utf-16", "utf-8", "latin-1", "cp1252"):
            try:
                content = raw_bytes.decode(encoding)
                logger.debug(f"Fallback encoding '{encoding}' succeeded for {txt_path}")
                break
            except (UnicodeDecodeError, LookupError):
                continue
        # Explicitly delete raw_bytes to help GC
        del raw_bytes

    if content is None:
        logger.warning(f"Could not decode {txt_path} with any known encoding")
        return [
            {
                "type": "error",
                "filename": sanitize_filename(os.path.basename(txt_path)),
                "message": "File encoding not supported (could not detect valid encoding)",
            }
        ]

    return [
        {
            "type": "text",
            "content": sanitize_text_content(content),
            "filename": sanitize_filename(os.path.basename(txt_path)),
        }
    ]


# --- EML Processing Helpers (Reduce Cognitive Complexity) ---


def _extract_eml_body(mail: Any) -> str:
    """Extract text body from parsed email, preferring plain text over HTML."""
    if mail.text_plain:
        return "\n".join(mail.text_plain)
    if mail.text_html:
        raw_html = "\n".join(mail.text_html)
        return _strip_html(raw_html)
    return mail.body or ""


def _decode_attachment_payload(
    payload: Any, original_filename: str
) -> tuple[bytes | None, str]:
    """
    Decode attachment payload from base64 string or raw bytes.

    Returns:
        Tuple of (decoded_bytes, error_type):
        - (bytes, "ok") on success
        - (None, "size_exceeded") if encoded size exceeds limit
        - (None, "decode_failed") if base64 decoding fails
    """
    if isinstance(payload, bytes):
        return payload, "ok"

    payload = payload.strip()

    # SECURITY: Check size BEFORE decoding to prevent Memory DoS
    if len(payload) > MAX_B64_STRING_LENGTH:
        logger.warning(
            f"Attachment '{original_filename}' exceeds size limit "
            f"(encoded size: {len(payload):,} bytes > {MAX_B64_STRING_LENGTH:,}). Skipping."
        )
        return None, "size_exceeded"

    # Valid base64 length modulo 4 can only be 0, 2, or 3.
    # 1 is impossible (6 bits) for full bytes.
    # 0: No padding needed.
    # 2: Needs "=="
    # 3: Needs "="

    # CRITICAL: Must remove whitespace (newlines, spaces) before length check.
    # EML files often wrap base64 at 76 chars with \n.
    # If we count \n, the length modulo is wrong.
    # Fast whitespace removal using translation table.
    payload = payload.translate(str.maketrans("", "", string.whitespace))

    mod = len(payload) % 4
    if mod == 1:
        # Impossible length for valid base64
        logger.warning(
            f"Invalid base64 length ({len(payload)} chars, 1 mod 4) in attachment '{original_filename}'"
        )
        return None, "decode_failed"
    elif mod == 2:
        payload += "=="
    elif mod == 3:
        payload += "="

    try:
        return base64.b64decode(payload, validate=True), "ok"
    except binascii.Error:
        logger.warning(f"Invalid base64 in attachment '{original_filename}'")
        return None, "decode_failed"


def _should_skip_tiny_image(
    decoded_payload: bytes, ext: str, original_filename: str, eml_path: str
) -> bool:
    """Check if attachment is a tiny image (signature/icon) that should be skipped."""
    if len(decoded_payload) >= TINY_IMAGE_THRESHOLD_BYTES:
        return False

    if ext not in TINY_IMAGE_EXTENSIONS:
        return False

    try:
        with Image.open(io.BytesIO(decoded_payload)) as img:
            width, height = img.size
            if width < TINY_IMAGE_DIMENSION_PX and height < TINY_IMAGE_DIMENSION_PX:
                logger.info(
                    f"Skipping tiny image '{original_filename}' "
                    f"({width}x{height}, {len(decoded_payload)} bytes) in {eml_path}"
                )
                return True
    except Exception as e:
        logger.warning(
            f"Could not check dimensions of small image {original_filename}: {e}"
        )

    return False


def _save_and_process_attachment(
    decoded_payload: bytes,
    original_filename: str,
    upload_folder: str,
    depth: int,
) -> List[Dict[str, Any]]:
    """Save attachment to disk and recursively process it."""
    safe_filename = sanitize_filename(original_filename) or "attachment.bin"

    # Prevent filename collisions with UUID prefix
    unique_prefix = uuid.uuid4().hex[:8]
    safe_filename = f"{unique_prefix}_{safe_filename}"

    local_path = os.path.join(upload_folder, safe_filename)

    with open(local_path, "wb") as f:
        f.write(decoded_payload)

    if not os.path.exists(local_path):
        return []

    attachment_parts = process_uploaded_file(local_path, upload_folder, depth=depth + 1)
    return (
        attachment_parts if isinstance(attachment_parts, list) else [attachment_parts]
    )


def _process_single_attachment(
    attachment: Dict[str, Any],
    eml_path: str,
    upload_folder: str,
    depth: int,
) -> List[Dict[str, Any]]:
    """
    Process a single email attachment.
    Returns list of parts (may be empty if skipped, or contain error dict).
    """
    original_filename = attachment.get("filename") or "untitled_attachment"
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower()

    # Skip excluded extensions
    if ext in EXCLUDED_EXTENSIONS:
        logger.info(
            f"Skipping excluded attachment type '{ext}' for file '{original_filename}' in {eml_path}"
        )
        return []

    payload = attachment.get("payload", "")
    if not payload:
        return []

    # Decode payload
    decoded_payload, decode_status = _decode_attachment_payload(
        payload, original_filename
    )
    if decode_status == "size_exceeded":
        # Original behavior: append error for size limit exceeded
        return [
            {
                "type": "error",
                "filename": original_filename,
                "message": f"Attachment too large (>{MAX_ATTACHMENT_SIZE_BYTES // (1024*1024)}MB)",
            }
        ]
    if decode_status == "decode_failed" or decoded_payload is None:
        # Original behavior: silently skip invalid base64
        return []

    # Double-check decoded size
    if len(decoded_payload) > MAX_ATTACHMENT_SIZE_BYTES:
        logger.warning(
            f"Attachment '{original_filename}' exceeds size limit "
            f"(decoded size: {len(decoded_payload):,} bytes). Skipping."
        )
        return [
            {
                "type": "error",
                "filename": original_filename,
                "message": f"Attachment too large (>{MAX_ATTACHMENT_SIZE_BYTES // (1024*1024)}MB)",
            }
        ]

    # Skip tiny images (signatures/icons)
    if _should_skip_tiny_image(decoded_payload, ext, original_filename, eml_path):
        return []

    # Save and process
    try:
        return _save_and_process_attachment(
            decoded_payload, original_filename, upload_folder, depth
        )
    except Exception as e:
        logger.error(f"Error processing attachment {original_filename}: {e}")
        return []


@handle_extraction_errors()
def process_eml_file(
    eml_path: str, upload_folder: str, depth: int = 0
) -> List[Dict[str, Any]]:
    """
    Processes an .eml file, extracting its text body and saving/processing attachments.
    Returns a FLAT LIST of dictionaries.
    """
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(
            f"Max recursion depth ({MAX_RECURSION_DEPTH}) reached for {eml_path}"
        )
        return [
            {
                "type": "error",
                "filename": os.path.basename(eml_path),
                "message": f"Max recursion depth ({MAX_RECURSION_DEPTH}) reached (nested attachments)",
            }
        ]

    mail = mailparser.parse_from_file(eml_path)
    all_parts: List[Dict[str, Any]] = []

    # Extract email body
    text_content = _extract_eml_body(mail)
    all_parts.append(
        {
            "type": "text",
            "content": sanitize_text_content(text_content),
            "filename": f"{sanitize_filename(os.path.basename(eml_path))} (body)",
            "original_filetype": "eml",
        }
    )

    # Process attachments with hard limit
    for i, attachment in enumerate(mail.attachments):
        if i >= MAX_EML_ATTACHMENTS:
            logger.warning(
                f"Attachment limit ({MAX_EML_ATTACHMENTS}) reached for {eml_path}"
            )
            all_parts.append(
                {
                    "type": "warning",
                    "filename": os.path.basename(eml_path),
                    "message": f"Remaining attachments skipped (scanned {MAX_EML_ATTACHMENTS} items)",
                }
            )
            break

        attachment_parts = _process_single_attachment(
            attachment, eml_path, upload_folder, depth
        )
        all_parts.extend(attachment_parts)

    return all_parts


def process_uploaded_file(
    filepath: str, upload_folder: str, depth: int = 0
) -> List[Dict[str, Any]]:
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    # Simple Dispatcher
    processors = {
        ".pdf": prepare_pdf_for_llm,
        EXT_PNG: prepare_image_for_llm,
        EXT_JPG: prepare_image_for_llm,
        EXT_JPEG: prepare_image_for_llm,
        EXT_WEBP: prepare_image_for_llm,
        EXT_GIF: prepare_image_for_llm,
        ".docx": extract_text_from_docx,
        ".xlsx": extract_text_from_xlsx,
        ".txt": extract_text_from_txt,
    }

    if ext == ".eml":
        return process_eml_file(filepath, upload_folder, depth=depth)

    if processor := processors.get(ext):
        result = processor(filepath)
        # Verify it is a list (POLA enforcement)
        return [result] if isinstance(result, dict) else result
    return [
        {
            "type": "unsupported",
            "filename": os.path.basename(filepath),
            "message": f"Unsupported file type: {ext}",
        }
    ]
