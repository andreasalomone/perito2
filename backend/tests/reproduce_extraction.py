import os
import sys
import fitz
from PIL import Image, ImageDraw
from docx import Document
import shutil
import logging

# Configure logging to show info
logging.basicConfig(level=logging.INFO)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import document_processor as dp

OUTPUT_DIR = "tests/temp_extraction_test"
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

def create_native_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a native PDF with selectable text. It needs to be longer than 50 characters to trigger the hybrid extraction logic.", fontsize=12)
    doc.save(path)
    doc.close()

def create_scanned_pdf(path):
    # Create image
    img = Image.new('RGB', (500, 200), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10,10), "This is a scanned PDF (image).", fill=(0,0,0))
    img_path = os.path.join(OUTPUT_DIR, "temp_scan.png")
    img.save(img_path)

    # Embed in PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=img_path)
    doc.save(path)
    doc.close()

def create_docx(path):
    doc = Document()
    doc.add_paragraph("This is a DOCX file.")
    doc.save(path)

def create_txt(path):
    with open(path, "w") as f:
        f.write("This is a TXT file.")

def create_eml(path):
    content = """From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: text/plain; charset="utf-8"

This is the email body.

--boundary
Content-Type: text/plain; name="attachment.txt"
Content-Disposition: attachment; filename="attachment.txt"
Content-Transfer-Encoding: base64

VGhpcyBpcyBhbiBhdHRhY2htZW50Lg==
--boundary--
"""
    with open(path, "w") as f:
        f.write(content)

def run_tests():
    files = {
        "native.pdf": create_native_pdf,
        "scanned.pdf": create_scanned_pdf,
        "test.docx": create_docx,
        "test.txt": create_txt,
        "test.eml": create_eml
    }

    print("--- Starting Extraction Tests ---")
    for filename, creator in files.items():
        filepath = os.path.join(OUTPUT_DIR, filename)
        creator(filepath)
        print(f"\nProcessing {filename}...")
        try:
            # We need to mock the upload folder for EML processing
            result = dp.process_uploaded_file(filepath, upload_folder=OUTPUT_DIR)
            print(f"Result for {filename}:")
            print(result)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    run_tests()
