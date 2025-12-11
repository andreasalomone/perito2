import base64
import binascii
import datetime
import functools
import io
import logging
import mimetypes
import os
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Set, TypeVar

import fitz  # PyMuPDF
import mailparser
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
    if not content:
        return content
    # Remove NULL bytes that PostgreSQL JSONB cannot handle
    return content.replace("\x00", "")


logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def handle_extraction_errors(
    default_return_value: Any = None,
) -> Callable[[F], F]:
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
    if not mime_type or not mime_type.startswith("image/"):
        if pil_format:
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
        if ext in [".jpg", ".jpeg"]:
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
                for event, elem in context:
                    # w:t is the tag for text in Word XML
                    if elem.tag.endswith("}t"):
                        if elem.text:
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
    """
    num = 0
    for c in col_label:
        if "A" <= c <= "Z":
            num = num * 26 + (ord(c) - ord("A") + 1)
    return num - 1


def _extract_col_from_ref(r_attr: str) -> str:
    """Extracts column letter from cell reference (e.g., 'AA12' -> 'AA')."""
    match = re.match(r"([A-Z]+)", r_attr)
    return match.group(1) if match else "A"  # Fallback


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
            if elem.tag.endswith("}t"):
                if elem.text:
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
    output_parts: List[str] = []
    total_chars = 0
    truncated = False

    try:
        # 1. Quick Validity Check
        if not zipfile.is_zipfile(xlsx_path):
            raise ValueError("File is not a valid zip/xlsx archive")

        with zipfile.ZipFile(xlsx_path, "r") as zf:

            # 2. Load Shared Strings (The most memory-intensive part)
            try:
                shared_strings = _parse_shared_strings(zf)
            except MemoryError as e:
                logger.warning(f"Rejected XLSX {xlsx_path}: {e}")
                return [
                    {
                        "type": "error",
                        "filename": sanitize_filename(os.path.basename(xlsx_path)),
                        "message": str(e),
                    }
                ]

            # 3. Identify Worksheets
            sheet_files = sorted(
                [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")]
            )

            if not sheet_files:
                return [
                    {
                        "type": "error",
                        "filename": sanitize_filename(os.path.basename(xlsx_path)),
                        "message": "No worksheets found in Excel file.",
                    }
                ]

            # 4. Stream Parse Worksheets
            for sheet_file in sheet_files:
                if truncated:
                    break

                sheet_name = os.path.basename(sheet_file).replace(".xml", "")
                output_parts.append(f"\n## Sheet: {sheet_name}\n\n")

                # Sparse Row Buffer: dict {col_index: value}
                row_data: Dict[int, str] = {}
                current_row_index = 0
                table_width = 0  # Determined by first valid row (header)
                is_first_valid_row = True  # Flag for header separator logic

                with zf.open(sheet_file) as f:
                    context = ET.iterparse(f, events=("end",))

                    for _, elem in context:
                        # <row> indicates end of a row
                        if elem.tag.endswith("}row"):
                            current_row_index += 1

                            # GUARD: Max Rows
                            if current_row_index > MAX_XLSX_SHEET_ROWS:
                                output_parts.append(
                                    f"\n*[TRUNCATED: > {MAX_XLSX_SHEET_ROWS:,} rows]*\n"
                                )
                                truncated = True
                                elem.clear()
                                break

                            # Finalize Row - build dense list from sparse dict
                            if row_data:
                                # Determine row width based on first valid row (header)
                                if is_first_valid_row:
                                    table_width = max(row_data.keys()) + 1
                                    table_width = min(
                                        table_width, MAX_COL_WIDTH
                                    )  # Safety Cap

                                # Build dense list from sparse dict
                                dense_row = []
                                for i in range(table_width):
                                    val = row_data.get(i, "")  # Empty for missing cells
                                    dense_row.append(val if val else "-")

                                # Markdown Table Formatting
                                line = "| " + " | ".join(dense_row) + " |\n"

                                # Add header separator after FIRST VALID ROW (not just row 1)
                                if is_first_valid_row:
                                    separator = (
                                        "| "
                                        + " | ".join(["---"] * table_width)
                                        + " |\n"
                                    )
                                    line += separator
                                    is_first_valid_row = False  # Latch the flag

                                # GUARD: Max Output Size
                                if total_chars + len(line) > MAX_XLSX_TEXT_OUTPUT:
                                    output_parts.append(
                                        "\n*[TRUNCATED: Output Size Limit]*\n"
                                    )
                                    truncated = True
                                    elem.clear()
                                    break

                                output_parts.append(line)
                                total_chars += len(line)
                                row_data.clear()  # Reset for next row

                            elem.clear()  # Free memory
                            continue

                        # <c> is a cell
                        if elem.tag.endswith("}c"):
                            # Get Column Index from cell reference (e.g., "B5" -> 1)
                            r_attr = elem.get("r")  # Cell reference like "B5"
                            if r_attr:
                                col_letter = _extract_col_from_ref(r_attr)
                                col_idx = _col_to_int(col_letter)
                            else:
                                # Fallback if 'r' is missing (rare)
                                col_idx = len(row_data)

                            # Security: Ignore extremely far columns (e.g. XFD)
                            if col_idx >= MAX_COL_WIDTH:
                                elem.clear()
                                continue

                            cell_type = elem.get("t")  # 's'=shared, 'n'=number, etc.
                            cell_val = ""

                            # Find the <v> (value) tag inside the cell
                            v_tag = elem.find("{*}v")  # Namespace wildcard

                            if v_tag is not None and v_tag.text:
                                raw_val = v_tag.text

                                if cell_type == "s":
                                    # Shared String Lookup
                                    try:
                                        idx = int(raw_val)
                                        if 0 <= idx < len(shared_strings):
                                            cell_val = shared_strings[idx]
                                        else:
                                            cell_val = "[ERR:REF]"
                                    except ValueError:
                                        cell_val = "[ERR:IDX]"

                                elif cell_type == "b":
                                    # Boolean
                                    cell_val = "TRUE" if raw_val == "1" else "FALSE"

                                elif cell_type == "str":
                                    # Inline string
                                    cell_val = raw_val

                                else:
                                    # Number / Date (stored as float)
                                    try:
                                        f_val = float(raw_val)
                                        # Heuristic: Excel dates between 20000 (1954) and 60000 (2064)
                                        if 20000 < f_val < 60000 and f_val == int(
                                            f_val
                                        ):
                                            cell_val = _excel_date_to_string(f_val)
                                        elif f_val == int(f_val):
                                            cell_val = str(int(f_val))
                                        else:
                                            cell_val = f"{f_val:.2f}"
                                    except ValueError:
                                        cell_val = raw_val

                            # Handle Inline Strings <is><t>val</t></is>
                            is_tag = elem.find("{*}is")
                            if is_tag is not None:
                                t_tag = is_tag.find("{*}t")
                                if t_tag is not None and t_tag.text:
                                    cell_val = t_tag.text

                            # Store in sparse dict by column index
                            clean_val = cell_val.strip().replace("|", "/")
                            if clean_val:
                                row_data[col_idx] = clean_val

                            elem.clear()  # Vital for memory

    except zipfile.BadZipFile:
        logger.error(f"Bad zip file: {xlsx_path}")
        return [
            {
                "type": "error",
                "filename": sanitize_filename(os.path.basename(xlsx_path)),
                "message": "Corrupted or invalid XLSX file",
            }
        ]
    except Exception as e:
        logger.error(f"Error extracting XLSX {xlsx_path}: {e}", exc_info=True)
        return [
            {
                "type": "error",
                "filename": sanitize_filename(os.path.basename(xlsx_path)),
                "message": f"Extraction failed: {str(e)}",
            }
        ]

    return [
        {
            "type": "text",
            "content": sanitize_text_content("".join(output_parts)),
            "filename": sanitize_filename(os.path.basename(xlsx_path)),
        }
    ]


@handle_extraction_errors()
def extract_text_from_txt(txt_path: str) -> List[Dict[str, Any]]:
    # Prevent OOM on maliciously large text files
    MAX_TXT_SIZE = 10 * 1024 * 1024  # 10MB
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

    # Try multiple encodings for email attachments (common non-UTF-8 sources)
    content = None
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(txt_path, "r", encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        logger.warning(f"Could not decode {txt_path} with any known encoding")
        return [
            {
                "type": "error",
                "filename": sanitize_filename(os.path.basename(txt_path)),
                "message": "File encoding not supported (not UTF-8, Latin-1, or Windows-1252)",
            }
        ]

    return [
        {
            "type": "text",
            "content": sanitize_text_content(content),
            "filename": sanitize_filename(os.path.basename(txt_path)),
        }
    ]


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

    # Extract plain text body (strip HTML to prevent LLM context pollution)
    text_content = ""
    if mail.text_plain:
        text_content = "\n".join(mail.text_plain)
    elif mail.text_html:
        # Use proper HTML parser to extract text (not regex)
        raw_html = "\n".join(mail.text_html)
        text_content = _strip_html(raw_html)
    else:
        text_content = mail.body if mail.body else ""

    all_parts.append(
        {
            "type": "text",
            "content": sanitize_text_content(text_content),
            "filename": f"{sanitize_filename(os.path.basename(eml_path))} (body)",
            "original_filetype": "eml",
        }
    )

    # Use StorageProvider to save attachments
    # storage = get_storage_provider() # Removed for now as we need local processing for extraction

    # --- Process Attachments (Hard Loop Limit with enumerate) ---
    # Using enumerate ensures we hard-stop after MAX_EML_ATTACHMENTS even if items are skipped
    # This prevents CPU exhaustion from 10,000 tiny images that get decoded but skipped
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

        # CRITICAL FIX: Handle case where 'filename' key exists but value is None
        # attachment.get("filename", "default") returns None if key exists with None value
        original_filename = attachment.get("filename") or "untitled_attachment"

        # Check for excluded extensions (use constant)
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        if ext in EXCLUDED_EXTENSIONS:
            logger.info(
                f"Skipping excluded attachment type '{ext}' for file '{original_filename}' in {eml_path}"
            )
            continue

        payload = attachment.get("payload", "")

        if not payload:
            continue

        try:
            if isinstance(payload, str):
                payload = payload.strip()

                # SECURITY CRITICAL: Check size BEFORE decoding to prevent Memory DoS
                # A 100MB base64 string would allocate ~75MB+ when decoded
                if len(payload) > MAX_B64_STRING_LENGTH:
                    logger.warning(
                        f"Attachment '{original_filename}' exceeds size limit "
                        f"(encoded size: {len(payload):,} bytes > {MAX_B64_STRING_LENGTH:,}). Skipping."
                    )
                    all_parts.append(
                        {
                            "type": "error",
                            "filename": original_filename,
                            "message": f"Attachment too large (>{MAX_ATTACHMENT_SIZE_BYTES // (1024*1024)}MB)",
                        }
                    )
                    continue

                # Fix base64 padding
                missing_padding = len(payload) % 4
                if missing_padding:
                    payload += "=" * (4 - missing_padding)

                try:
                    decoded_payload = base64.b64decode(payload)
                except binascii.Error:
                    logger.warning(
                        f"Invalid base64 in attachment '{original_filename}'"
                    )
                    continue
            else:
                # Payload might already be bytes in some parsers
                decoded_payload = payload

            # SECURITY: Double-check decoded size (covers both string and bytes paths)
            if len(decoded_payload) > MAX_ATTACHMENT_SIZE_BYTES:
                logger.warning(
                    f"Attachment '{original_filename}' exceeds size limit "
                    f"(decoded size: {len(decoded_payload):,} bytes). Skipping."
                )
                all_parts.append(
                    {
                        "type": "error",
                        "filename": original_filename,
                        "message": f"Attachment too large (>{MAX_ATTACHMENT_SIZE_BYTES // (1024*1024)}MB)",
                    }
                )
                continue

            # --- TINY IMAGE FILTER (Signatures/Icons) ---
            if len(decoded_payload) < TINY_IMAGE_THRESHOLD_BYTES:
                if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                    try:
                        with Image.open(io.BytesIO(decoded_payload)) as img:
                            width, height = img.size
                            if (
                                width < TINY_IMAGE_DIMENSION_PX
                                and height < TINY_IMAGE_DIMENSION_PX
                            ):
                                logger.info(
                                    f"Skipping tiny image '{original_filename}' "
                                    f"({width}x{height}, {len(decoded_payload)} bytes) in {eml_path}"
                                )
                                continue
                    except Exception as e:
                        # If we can't parse it as an image, just proceed (safe failure)
                        logger.warning(
                            f"Could not check dimensions of small image {original_filename}: {e}"
                        )
            # --------------------------------------------

            # Use the robust sanitize_filename utility
            safe_filename = sanitize_filename(original_filename)
            if not safe_filename:
                safe_filename = "attachment.bin"

            # FIX: Prevent filename collisions in recursive processing
            # Prepend a short UUID to ensure uniqueness in the flat upload folder
            unique_prefix = uuid.uuid4().hex[:8]
            safe_filename = f"{unique_prefix}_{safe_filename}"

            # Save to local temp folder for recursive processing
            # This ensures we can read it back with fitz/openpyxl/etc.
            local_path = os.path.join(upload_folder, safe_filename)

            with open(local_path, "wb") as f:
                f.write(decoded_payload)

            # Recurse
            if os.path.exists(local_path):
                attachment_parts = process_uploaded_file(
                    local_path, upload_folder, depth=depth + 1
                )
                if isinstance(attachment_parts, list):
                    all_parts.extend(attachment_parts)
                else:
                    all_parts.append(attachment_parts)

            # Optional: If we wanted to persist to GCS, we would do it here.
            # But for report generation, extracting the content is the primary goal.

        except Exception as e:
            logger.error(f"Error processing attachment {original_filename}: {e}")

    return all_parts


def process_uploaded_file(
    filepath: str, upload_folder: str, depth: int = 0
) -> List[Dict[str, Any]]:
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    # Simple Dispatcher
    processors = {
        ".pdf": prepare_pdf_for_llm,
        ".png": prepare_image_for_llm,
        ".jpg": prepare_image_for_llm,
        ".jpeg": prepare_image_for_llm,
        ".webp": prepare_image_for_llm,
        ".gif": prepare_image_for_llm,
        ".docx": extract_text_from_docx,
        ".xlsx": extract_text_from_xlsx,
        ".txt": extract_text_from_txt,
    }

    if ext == ".eml":
        return process_eml_file(filepath, upload_folder, depth=depth)

    processor = processors.get(ext)

    if processor:
        result = processor(filepath)
        # Verify it is a list (POLA enforcement)
        if isinstance(result, dict):
            return [result]
        return result

    return [
        {
            "type": "unsupported",
            "filename": os.path.basename(filepath),
            "message": f"Unsupported file type: {ext}",
        }
    ]
