import logging
from typing import Optional

from core.database import db
from core.models import DocumentLog, ReportLog, ReportStatus

logger = logging.getLogger(__name__)


def create_initial_report_log() -> ReportLog:
    """Creates and returns a new ReportLog entry."""
    report_log = ReportLog()
    db.session.add(report_log)
    db.session.commit()
    # Refresh to get the ID and other defaults populated before detaching/returning
    db.session.refresh(report_log)
    # Expunge to allow usage outside this session (though it will be detached)
    db.session.expunge(report_log)
    logger.info(f"Created initial ReportLog entry with ID: {report_log.id}")
    return report_log


def update_report_status(
    report_log_id: int,
    status: ReportStatus,
    error_message: Optional[str] = None,
    llm_raw_response: Optional[str] = None,
    final_report_text: Optional[str] = None,
    generation_time_seconds: Optional[float] = None,
    api_cost_usd: Optional[float] = None,
    prompt_token_count: Optional[int] = None,
    candidates_token_count: Optional[int] = None,
    total_token_count: Optional[int] = None,
    cached_content_token_count: Optional[int] = None,
) -> None:
    """Updates the status and other fields of a ReportLog."""
    report_log = db.session.get(ReportLog, report_log_id)
    if not report_log:
        logger.error(f"ReportLog with ID {report_log_id} not found for update.")
        return

    report_log.status = status
    if error_message is not None:
        report_log.error_message = error_message
    if llm_raw_response is not None:
        report_log.llm_raw_response = llm_raw_response
    if final_report_text is not None:
        report_log.final_report_text = final_report_text
    if generation_time_seconds is not None:
        report_log.generation_time_seconds = generation_time_seconds
    if api_cost_usd is not None:
        report_log.api_cost_usd = api_cost_usd
    if prompt_token_count is not None:
        report_log.prompt_token_count = prompt_token_count
    if candidates_token_count is not None:
        report_log.candidates_token_count = candidates_token_count
    if total_token_count is not None:
        report_log.total_token_count = total_token_count
    if cached_content_token_count is not None:
        report_log.cached_content_token_count = cached_content_token_count

    db.session.commit()


def create_document_log(
    report_id: int, original_filename: str, stored_filepath: str, file_size_bytes: int
) -> DocumentLog:
    """Creates and returns a new DocumentLog entry."""
    doc_log = DocumentLog(
        report_id=report_id,
        original_filename=original_filename,
        stored_filepath=stored_filepath,
        file_size_bytes=file_size_bytes,
    )
    db.session.add(doc_log)
    db.session.commit()
    db.session.refresh(doc_log)
    db.session.expunge(doc_log)
    return doc_log


def get_report_log(report_log_id: int) -> Optional[ReportLog]:
    """Retrieves a ReportLog by ID."""
    report_log = db.session.get(ReportLog, report_log_id)
    if report_log:
        # Expunge to allow access to loaded attributes after session closes
        db.session.expunge(report_log)
    return report_log


def update_document_log(
    document_id: str,
    status: Optional[str] = None,
    extracted_content_length: Optional[int] = None,
    error_message: Optional[str] = None,
    file_type: Optional[str] = None,
    extraction_method: Optional[str] = None,
) -> None:
    """Updates a DocumentLog entry."""
    doc_log = db.session.get(DocumentLog, document_id)
    if not doc_log:
        logger.error(f"DocumentLog with ID {document_id} not found for update.")
        return

    if status:
        # Convert string to Enum if necessary, or assume caller passes valid Enum/string
        # If status is passed as string "success", map it to ExtractionStatus.SUCCESS
        # If it's already an Enum, use it.
        if isinstance(status, str):
            try:
                # Import here to avoid circular imports if any, or just use the model's enum
                from core.models import ExtractionStatus

                doc_log.extraction_status = ExtractionStatus(status)
            except ValueError:
                logger.warning(
                    f"Invalid status '{status}' for DocumentLog {document_id}"
                )
        else:
            doc_log.extraction_status = status

    if extracted_content_length is not None:
        doc_log.extracted_content_length = extracted_content_length

    if error_message is not None:
        doc_log.error_message = error_message

    if file_type is not None:
        doc_log.file_type = file_type

    if extraction_method is not None:
        doc_log.extraction_method = extraction_method

    db.session.commit()
