import fitz
import os

def test_hybrid_capability():
    native_pdf = "tests/temp_extraction_test/native.pdf"
    scanned_pdf = "tests/temp_extraction_test/scanned.pdf"

    print(f"Testing Native PDF: {native_pdf}")
    if os.path.exists(native_pdf):
        doc = fitz.open(native_pdf)
        text = ""
        for page in doc:
            text += page.get_text()
        print(f"Extracted Text length: {len(text)}")
        print(f"Extracted Text preview: {text[:50]}...")
        if len(text.strip()) > 0:
            print("✅ Native PDF detected (has text).")
        else:
            print("❌ Native PDF NOT detected as text.")
    else:
        print("⚠️ Native PDF file not found. Run reproduce_extraction.py first.")

    print(f"\nTesting Scanned PDF: {scanned_pdf}")
    if os.path.exists(scanned_pdf):
        doc = fitz.open(scanned_pdf)
        text = ""
        for page in doc:
            text += page.get_text()
        print(f"Extracted Text length: {len(text)}")
        print(f"Extracted Text preview: {text[:50]}...")
        if len(text.strip()) == 0:
            print("✅ Scanned PDF detected (no text).")
        else:
            print(f"⚠️ Scanned PDF has text? (Length: {len(text)})")
    else:
        print("⚠️ Scanned PDF file not found. Run reproduce_extraction.py first.")

if __name__ == "__main__":
    test_hybrid_capability()
