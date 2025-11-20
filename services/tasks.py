import logging
import os
from typing import List

from core.celery_app import celery_app
from core.models import ReportStatus
import llm_handler
from services import db_service, file_service

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def generate_report_task(self, report_id: int, file_paths: List[str], original_filenames: List[str]):
    """
    Celery task to process files and generate a report asynchronously.
    """
    # Import app here to avoid circular imports
    from app import app

    with app.app_context():
        logger.info(f"Starting background task for report {report_id} with files: {file_paths}")
        
        try:
            # Update status to PROCESSING
            db_service.update_report_status(report_id, ReportStatus.PROCESSING)

            all_extracted_text = ""
            processed_files_count = 0
            total_text_length = 0
            
            # Process each file
            for filepath, original_filename in zip(file_paths, original_filenames):
                logger.info(f"Processing file: {filepath}")
                
                # Process the file
                result = file_service.process_file_from_path(
                    filepath, original_filename, total_text_length
                )
                
                if result.success and result.data:
                    # Extract text from processed entries
                    entries = result.data.get("processed_entries", [])
                    for entry in entries:
                        if entry.get("type") == "text" and entry.get("content"):
                            all_extracted_text += entry["content"] + "\n\n"
                    
                    total_text_length += result.data.get("text_length_added", 0)
                    processed_files_count += 1
                else:
                    logger.warning(f"Failed to process file {filepath}: {result.messages}")

            if not all_extracted_text.strip():
                logger.warning(f"No text extracted for report {report_id}")
                db_service.update_report_status(report_id, ReportStatus.ERROR, error_message="No text could be extracted from the uploaded files.")
                return

            # Generate Report via LLM (use sync wrapper)
            logger.info(f"Generating report for report {report_id} with {len(all_extracted_text)} chars")
            report_content = llm_handler.generate_report_from_content_sync(
                processed_files=[{"type": "text", "content": all_extracted_text}]
            )
            
            if report_content:
                # Update status to COMPLETED and save content
                db_service.update_report_status(
                    report_id,
                    ReportStatus.SUCCESS,
                    llm_raw_response=report_content,
                    final_report_text=report_content
                )
                logger.info(f"Report {report_id} generated successfully.")
            else:
                db_service.update_report_status(report_id, ReportStatus.ERROR, error_message="LLM failed to generate report.")
                logger.error(f"LLM returned empty content for report {report_id}")

        except Exception as e:
            logger.error(f"Error in generate_report_task for report {report_id}: {e}", exc_info=True)
            db_service.update_report_status(report_id, ReportStatus.ERROR, error_message=str(e))
        
        finally:
            # Cleanup temporary files
            for filepath in file_paths:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Deleted temporary file: {filepath}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to delete temp file {filepath}: {cleanup_error}")
