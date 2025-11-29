import os
import uuid
import shutil
import tempfile
import pathlib
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import ReportLog, ReportStatus
from services.gcs_service import download_file_to_temp, get_storage_client
from config import settings
from services import document_processor, llm_handler, docx_generator

async def generate_report_logic(report_id: str, user_id: str, file_paths: list, db: Session):
    # 1. Setup - Get Report Record
    report = db.query(ReportLog).filter(ReportLog.id == report_id).first()
    if not report:
        print("Report not found in DB")
        return

    # Update status
    report.status = ReportStatus.PROCESSING
    report.current_step = "processing_files"
    # Ensure progress_logs is valid
    current_logs = report.progress_logs if report.progress_logs else []
    report.progress_logs = current_logs + [{"timestamp": str(datetime.now()), "message": "Inizio analisi documenti..."}]
    
    db.commit()

    tmp_dir = tempfile.mkdtemp()
    processed_data_for_llm = []
    
    try:
        # 2. Process Each File
        for idx, gcs_path in enumerate(file_paths):
            # FIX: Force extraction of extension using pathlib
            # This handles spaces and dots in filenames correctly
            suffix = pathlib.Path(gcs_path).suffix
            if not suffix:
                suffix = ".tmp" # Fallback
                
            local_filename = f"file_{idx}_{uuid.uuid4()}{suffix}"
            local_path = os.path.join(tmp_dir, local_filename)
            
            print(f"Downloading {gcs_path} to {local_path}...")
            download_file_to_temp(gcs_path, local_path)
            
            # Run extraction
            processed = document_processor.process_uploaded_file(local_path, tmp_dir)
            
            if isinstance(processed, list):
                processed_data_for_llm.extend(processed)
            else:
                processed_data_for_llm.append(processed)

        # 3. Generate with Gemini
        report.current_step = "generating_ai"
        current_logs = report.progress_logs
        report.progress_logs = current_logs + [{"timestamp": str(datetime.now()), "message": "Generazione testo con Gemini 2.5..."}]
        db.commit()
        
        report_text, cost, token_usage = await llm_handler.generate_report_from_content(
            processed_files=processed_data_for_llm
        )

        # 4. Generate DOCX
        print("Generating DOCX...")
        docx_stream = docx_generator.create_styled_docx(report_text)
        
        # 5. Upload Result
        bucket_name = settings.STORAGE_BUCKET_NAME
        blob_name = f"reports/{user_id}/{report_id}/Perizia_Finale.docx"
        
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(docx_stream, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
        # Construct proper Authenticated URL or Storage Path
        final_docx_path = f"gs://{bucket_name}/{blob_name}"

        # 6. Save Success
        report.status = ReportStatus.SUCCESS
        report.final_report_text = report_text
        report.llm_raw_response = report_text
        report.final_docx_path = final_docx_path
        report.current_step = "completed"
        report.api_cost_usd = cost
        
        final_logs = report.progress_logs + [{"timestamp": str(datetime.now()), "message": "Generazione completata."}]
        report.progress_logs = final_logs
        
        db.commit()
        print("✅ Report generation completed successfully.")

    except Exception as e:
        print(f"❌ Error during generation: {e}")
        report.status = ReportStatus.ERROR
        report.error_message = str(e)
        db.commit()
        raise e 
    finally:
        shutil.rmtree(tmp_dir)