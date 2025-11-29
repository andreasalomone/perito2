import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import llm_handler
from google.genai import types

async def run_verification():
    print("--- Starting Data Flow Verification ---")

    # 1. Setup Mock Data (Simulating output of document_processor)
    processed_files = [
        # Native PDF (Hybrid: Vision + Text)
        {"type": "vision", "path": "/tmp/native.pdf", "mime_type": "application/pdf", "filename": "native.pdf"},
        {"type": "text", "content": "Extracted text from native PDF", "filename": "native.pdf (extracted text)"},

        # Scanned PDF (Vision only)
        {"type": "vision", "path": "/tmp/scanned.pdf", "mime_type": "application/pdf", "filename": "scanned.pdf"},
        {"type": "vision", "path": "/tmp/image.png", "mime_type": "image/png", "filename": "image.png"},
        
        # Text Files
        {"type": "text", "content": "Content of doc1", "filename": "doc1.docx"},
        {"type": "text", "content": "Content of doc2", "filename": "doc2.docx"},
        {"type": "text", "content": "Email body content", "filename": "email.eml (body)"},
        {"type": "text", "content": "Attachment content", "filename": "attachment.txt"},
        
        # Unsupported/Error
        {"type": "unsupported", "filename": "data.xml", "message": "XML not supported"} 
    ]

    # 2. Mock Dependencies
    
    # Mock Gemini Client
    mock_client = MagicMock()
    
    # Mock File Upload Service
    # We need to mock upload_vision_files to return fake File objects
    mock_file_obj_1 = types.File(name="files/native_pdf", uri="https://files/native_pdf")
    mock_file_obj_2 = types.File(name="files/scanned_pdf", uri="https://files/scanned_pdf")
    mock_file_obj_3 = types.File(name="files/image_png", uri="https://files/image_png")
    
    expected_uploaded_files = [mock_file_obj_1, mock_file_obj_2, mock_file_obj_3]
    
    with patch("services.llm.file_upload_service.upload_vision_files", new_callable=AsyncMock) as mock_upload, \
         patch("services.llm.generation_service.generate_with_fallback", new_callable=AsyncMock) as mock_generate, \
         patch("services.llm.file_upload_service.cleanup_uploaded_files", new_callable=AsyncMock) as mock_cleanup, \
         patch("services.llm.cache_service.get_or_create_prompt_cache", return_value=None), \
         patch("google.genai.Client", return_value=mock_client):

        # Setup mock returns
        mock_upload.return_value = (expected_uploaded_files, ["files/native_pdf", "files/scanned_pdf", "files/image_png"], [])
        
        mock_response = MagicMock()
        mock_response.text = "Report Generated Successfully"
        mock_response.usage_metadata = {}
        mock_generate.return_value = mock_response

        # 3. Run the Function
        print("Calling generate_report_from_content...")
        report, cost = await llm_handler.generate_report_from_content(processed_files)

        # 4. Verify Results
        print("\n--- Verification Results ---")
        
        # Check Uploads
        print(f"Upload Service Called: {mock_upload.called}")
        if mock_upload.called:
            args, _ = mock_upload.call_args
            files_passed_to_upload = args[1]
            vision_files_count = sum(1 for f in files_passed_to_upload if f['type'] == 'vision')
            print(f"Vision files passed to upload: {vision_files_count} (Expected: 3)")
            if vision_files_count == 3:
                print("✅ Vision file upload count matches.")
            else:
                print("❌ Vision file upload count MISMATCH.")

        # Check Generation Prompt
        print(f"Generation Service Called: {mock_generate.called}")
        if mock_generate.called:
            _, kwargs = mock_generate.call_args
            contents = kwargs.get('contents', [])
            
            print(f"Total prompt parts: {len(contents)}")
            
            # Analyze Prompt Content
            vision_files_in_prompt = 0
            text_content_found = []
            
            for part in contents:
                if isinstance(part, types.File):
                    vision_files_in_prompt += 1
                elif isinstance(part, str):
                    if "Content of doc1" in part: text_content_found.append("doc1.docx")
                    if "Content of doc2" in part: text_content_found.append("doc2.docx")
                    if "Email body content" in part: text_content_found.append("email.eml")
                    if "Attachment content" in part: text_content_found.append("attachment.txt")
                    if "XML not supported" in part: text_content_found.append("data.xml (warning)")
                    if "Extracted text from native PDF" in part: text_content_found.append("native.pdf (extracted text)")

            print(f"Vision File objects in prompt: {vision_files_in_prompt} (Expected: 3)")
            if vision_files_in_prompt == 3:
                print("✅ Vision files correctly embedded in prompt.")
            else:
                print("❌ Vision files MISSING from prompt.")

            print(f"Text contents found in prompt: {text_content_found}")
            expected_texts = ["doc1.docx", "doc2.docx", "email.eml", "attachment.txt", "data.xml (warning)", "native.pdf (extracted text)"]
            if all(t in str(text_content_found) for t in expected_texts): # Loose check
                 print("✅ All expected text content found in prompt.")
            else:
                 print("❌ Some text content is MISSING.")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(run_verification())
