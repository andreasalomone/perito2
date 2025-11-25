import logging
import os
from typing import List

import llm_handler
from core.celery_app import celery_app
from core.models import ReportStatus
from services import db_service, file_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def generate_report_task(
    self,
    report_id: int,
    file_paths: List[str],
    original_filenames: List[str],
    document_log_ids: List[str],
):
    """
    Celery task to process files and generate a report asynchronously.
    """
    # Import app here to avoid circular imports
    # (app.py imports report_service, which imports this task)
    try:
        from app import app
    except ImportError as e:
        import sys
        import os
        logger.error(f"Failed to import app: {e}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"sys.path: {sys.path}")
        raise e

    with app.app_context():
        logger.info(
            f"Starting background task for report {report_id} with files: {file_paths}"
        )

        try:
            # Update status to PROCESSING
            db_service.update_report_status(report_id, ReportStatus.PROCESSING)

            all_extracted_text = ""
            final_processed_files = []
            processed_files_count = 0
            total_text_length = 0

            # Process each file
            for filepath, original_filename, doc_log_id in zip(
                file_paths, original_filenames, document_log_ids
            ):
                logger.info(f"Processing file: {filepath}")

                # Process the file
                result = file_service.process_file_from_path(
                    filepath, original_filename, total_text_length
                )

                file_ext = (
                    os.path.splitext(original_filename)[1].lower().replace(".", "")
                )

                if result.success and result.data:
                    # Extract text from processed entries
                    entries = result.data.get("processed_entries", [])

                    # Collect all entries (text and vision)
                    final_processed_files.extend(entries)

                    file_extracted_text_len = 0

                    for entry in entries:
                        if entry.get("type") == "text" and entry.get("content"):
                            content = entry["content"]
                            all_extracted_text += content + "\n\n"
                            file_extracted_text_len += len(content)

                    total_text_length += result.data.get("text_length_added", 0)
                    processed_files_count += 1

                    # Update DocumentLog with success
                    extraction_method = "vision" if any(e.get("type") == "vision" for e in entries) else "text"
                    db_service.update_document_log(
                        document_id=doc_log_id,
                        status="success",
                        extracted_content_length=file_extracted_text_len,
                        file_type=file_ext,
                        extraction_method=extraction_method,
                    )
                else:
                    error_msg = "; ".join([m.message for m in result.messages])
                    logger.warning(
                        f"Failed to process file {filepath}: {result.messages}"
                    )
                    # Update DocumentLog with error
                    db_service.update_document_log(
                        document_id=doc_log_id,
                        status="error",
                        error_message=error_msg,
                        file_type=file_ext,
                    )

            if not all_extracted_text.strip() and not any(
                f.get("type") == "vision" for f in final_processed_files
            ):
                logger.warning(
                    f"No text extracted and no vision files found for report {report_id}"
                )
                db_service.update_report_status(
                    report_id,
                    ReportStatus.ERROR,
                    error_message="No content (text or vision) could be processed from the uploaded files.",
                )
                return

            # Generate Report via LLM (use sync wrapper)
            logger.info(
                f"Generating report for report {report_id} with {len(final_processed_files)} file parts ({len(all_extracted_text)} chars of text)"
            )
            report_content, api_cost_usd = (
                llm_handler.generate_report_from_content_sync(
                    processed_files=final_processed_files
                )
            )

            if report_content:
                # Update status to COMPLETED and save content
                db_service.update_report_status(
                    report_id,
                    ReportStatus.SUCCESS,
                    llm_raw_response=report_content,
                    final_report_text=report_content,
                    api_cost_usd=api_cost_usd,
                )
                logger.info(f"Report {report_id} generated successfully.")
            else:
                db_service.update_report_status(
                    report_id,
                    ReportStatus.ERROR,
                    error_message="LLM failed to generate report.",
                )
                logger.error(f"LLM returned empty content for report {report_id}")

        except Exception as e:
            logger.error(
                f"Error in generate_report_task for report {report_id}: {e}",
                exc_info=True,
            )
            db_service.update_report_status(
                report_id, ReportStatus.ERROR, error_message=str(e)
            )

        finally:
            # Cleanup temporary files
            for filepath in file_paths:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Deleted temporary file: {filepath}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to delete temp file {filepath}: {cleanup_error}"
                    )
