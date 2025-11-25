import asyncio
import logging
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_flow():
    print("--- Starting Multimodal Data Flow Verification ---")

    # Ensure modules are imported so they can be patched
    import services.db_service
    import services.file_service

    # We patch the modules where they are defined to ensure all importers get the mock
    with patch("services.db_service") as mock_db_module, \
         patch("services.file_service") as mock_file_service_module, \
         patch("services.llm.file_upload_service.upload_vision_files", new_callable=AsyncMock) as mock_upload, \
         patch("services.llm.cache_service.get_or_create_prompt_cache") as mock_cache, \
         patch("services.llm.generation_service.generate_with_fallback", new_callable=AsyncMock) as mock_generate, \
         patch("google.genai.Client") as MockClient:

        # Setup Mocks for services.file_service
        
        # PDF: Vision + Text
        pdf_result = MagicMock()
        pdf_result.success = True
        pdf_result.data = {
            "processed_entries": [
                {"type": "vision", "path": "/tmp/doc.pdf", "mime_type": "application/pdf", "filename": "doc.pdf"},
                {"type": "text", "content": "PDF Text Content", "filename": "doc.pdf (text)"}
            ],
            "text_length_added": 100
        }

        # Image: Vision only
        img_result = MagicMock()
        img_result.success = True
        img_result.data = {
            "processed_entries": [
                {"type": "vision", "path": "/tmp/img.png", "mime_type": "image/png", "filename": "img.png"}
            ],
            "text_length_added": 0
        }

        # DOCX: Text only
        docx_result = MagicMock()
        docx_result.success = True
        docx_result.data = {
            "processed_entries": [
                {"type": "text", "content": "DOCX Text Content", "filename": "doc.docx"}
            ],
            "text_length_added": 50
        }

        mock_file_service_module.process_file_from_path.side_effect = [pdf_result, img_result, docx_result]

        # Mock Cache Service
        mock_cache.return_value = "cachedContents/test-cache-123"

        # Mock Upload Service
        mock_file_obj_pdf = types.File(name="files/pdf_uri", uri="https://pdf_uri")
        mock_file_obj_img = types.File(name="files/img_uri", uri="https://img_uri")
        mock_upload.return_value = ([mock_file_obj_pdf, mock_file_obj_img], ["files/pdf_uri", "files/img_uri"], [])

        # Mock Generation Service
        mock_generate.return_value = MagicMock(text="Generated Report Content", usage_metadata={})

        # Mock DB Service to prevent errors
        mock_db_module.update_report_status = MagicMock()
        mock_db_module.update_document_log = MagicMock()

        # Import services.tasks AFTER patching
        # If it was already imported, we might need to reload, but since we patched the source modules
        # (services.db_service, services.file_service), the import in tasks.py should pick up the mocks
        # if tasks.py hasn't been imported yet.
        # If it has, we might need to patch services.tasks.db_service explicitly if it did 'from x import y'.
        # tasks.py does 'from services import db_service'.
        # So patching 'services.db_service' should work if we do it before import.
        
        if 'services.tasks' in sys.modules:
            del sys.modules['services.tasks']
        
        import services.tasks
        
        # Mock app context in tasks.py
        # tasks.py imports app inside the function. We need to mock app.app
        with patch("app.app") as mock_app:
            mock_app.app_context.return_value.__enter__.return_value = None
            
            # Execute the Task Logic
            print("\n[Action] Executing generate_report_task logic...")
            
            services.tasks.generate_report_task(
                report_id=1,
                file_paths=["/tmp/doc.pdf", "/tmp/img.png", "/tmp/doc.docx"],
                original_filenames=["doc.pdf", "img.png", "doc.docx"],
                document_log_ids=["1", "2", "3"]
            )

        # --- VERIFICATION ---

        print("\n[Verification] Checking File Processing...")
        assert mock_file_service_module.process_file_from_path.call_count == 3
        print("✅ Processed 3 files.")

        print("\n[Verification] Checking Vision Uploads...")
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        processed_files_arg = call_args[0][1]
        
        vision_files_count = sum(1 for f in processed_files_arg if f.get("type") == "vision")
        print(f"   Vision files sent to upload: {vision_files_count}")
        assert vision_files_count == 2
        print("✅ Correctly identified and uploaded 2 vision files.")

        print("\n[Verification] Checking Prompt Generation...")
        mock_generate.assert_called_once()
        gen_args = mock_generate.call_args
        
        # Check Config for Cache
        config = gen_args.kwargs.get('config') or gen_args[0][3]
        print(f"   Generation Config Cached Content: {getattr(config, 'cached_content', None)}")
        assert getattr(config, 'cached_content', None) == "cachedContents/test-cache-123"
        print("✅ Cache name correctly present in generation config.")

        # Check Contents for Multimodal Parts
        contents = gen_args.kwargs.get('contents') or gen_args[0][2]
        print(f"   Total content parts sent to LLM: {len(contents)}")
        
        has_pdf_text = any("PDF Text Content" in str(p) for p in contents)
        has_docx_text = any("DOCX Text Content" in str(p) for p in contents)
        has_vision_files = any(isinstance(p, types.File) for p in contents)
        
        print(f"   Contains PDF Text: {has_pdf_text}")
        print(f"   Contains DOCX Text: {has_docx_text}")
        print(f"   Contains Vision Files: {has_vision_files}")
        
        assert has_pdf_text
        assert has_docx_text
        assert has_vision_files
        print("✅ LLM received both extracted text and vision file objects.")

        # Verify Static Prompts are ABSENT (due to cache)
        has_static_prompt = any("Sei un assistente esperto" in str(p) for p in contents)
        print(f"   Contains Static System Prompt: {has_static_prompt}")
        assert not has_static_prompt
        print("✅ Static prompts correctly excluded (relying on cache).")

        print("\n--- Verification SUCCESS: End-to-End Multimodal Flow is Correct ---")

if __name__ == "__main__":
    verify_flow()
