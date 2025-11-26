from typing import Any, Dict, Tuple

from flask_sqlalchemy.pagination import Pagination
from sqlalchemy import func, text

from core.database import db
from core.models import DocumentLog, ExtractionStatus, ReportLog, ReportStatus
from core.prompt_config import prompt_manager


def get_prompt_content(prompt_name: str) -> Tuple[str, bool]:
    """
    Reads the content of a specific prompt file.

    Args:
        prompt_name: The key of the prompt.

    Returns:
        A tuple containing the file content (str) and a boolean indicating success.
    """
    return prompt_manager.get_prompt_content(prompt_name)


def update_prompt_content(prompt_name: str, content: str) -> Tuple[str, bool]:
    """
    Writes new content to a specific prompt file.

    Args:
        prompt_name: The key of the prompt.
        content: The new content to write to the file.

    Returns:
        A tuple containing a status message and a boolean indicating success.
    """
    return prompt_manager.update_prompt_content(prompt_name, content)


def get_all_prompts() -> Dict[str, str]:
    """
    Reads the content of all configured prompt files.

    Returns:
        A dictionary where keys are prompt names and values are their content.
        If a file cannot be read, the value will be an error message.
    """
    return prompt_manager.get_all_prompts()


# --- Report Inspector Services ---
def get_paginated_reports(page: int = 1, per_page: int = 20) -> Pagination:
    """
    Fetches a paginated list of all reports from the database,
    ordered by most recent first.
    """
    return (
        db.session.query(ReportLog)
        .order_by(ReportLog.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )


def get_report_by_id(report_id: str) -> ReportLog:
    """
    Fetches a single report and its associated documents by its ID.
    """
    return db.session.query(ReportLog).filter_by(id=report_id).first_or_404()


def get_paginated_documents(page: int = 1, per_page: int = 20) -> Pagination:
    """
    Fetches a paginated list of all documents from the database,
    ordered by most recent first (using report creation time as proxy if needed,
    or just by ID if no timestamp on doc).
    Actually, DocumentLog doesn't have a created_at, but it's linked to ReportLog.
    Let's join to order by report date.
    """
    return (
        db.session.query(DocumentLog)
        .join(ReportLog)
        .order_by(ReportLog.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )


# --- Dashboard Statistics Services ---


def get_dashboard_stats() -> Dict[str, Any]:
    """
    Fetches statistics for the admin dashboard from the database.
    """
    try:
        reports_generated = (
            db.session.query(ReportLog).filter_by(status=ReportStatus.SUCCESS).count()
        )
        processing_errors = (
            db.session.query(ReportLog).filter_by(status=ReportStatus.ERROR).count()
        )

        # func.sum returns None if there are no rows, so we handle that.
        total_cost_query = db.session.query(func.sum(ReportLog.api_cost_usd)).scalar()
        total_cost = total_cost_query or 0.0

        # func.avg also returns None for no rows.
        avg_gen_time_query = (
            db.session.query(func.avg(ReportLog.generation_time_seconds))
            .filter_by(status=ReportStatus.SUCCESS)
            .scalar()
        )
        avg_gen_time = avg_gen_time_query or 0

        # Token usage stats
        total_prompt_tokens = (
            db.session.query(func.sum(ReportLog.prompt_token_count)).scalar() or 0
        )
        total_candidates_tokens = (
            db.session.query(func.sum(ReportLog.candidates_token_count)).scalar() or 0
        )
        total_tokens = (
            db.session.query(func.sum(ReportLog.total_token_count)).scalar() or 0
        )
        total_cached_tokens = (
            db.session.query(func.sum(ReportLog.cached_content_token_count)).scalar()
            or 0
        )

        # Calculate non-cached prompt tokens (Prompt - Cached)
        # Note: prompt_token_count includes cached tokens in Gemini API usage metadata?
        # Let's assume prompt_token_count is TOTAL input tokens.
        # So non-cached input = prompt_token_count - cached_content_token_count.
        total_non_cached_prompt_tokens = total_prompt_tokens - total_cached_tokens

        return {
            "reports_generated": reports_generated,
            "api_cost_monthly_est": f"${total_cost:.2f}",
            "avg_generation_time_secs": f"{avg_gen_time:.0f}s",
            "processing_errors": processing_errors,
            "total_documents": db.session.query(DocumentLog).count(),
            "extraction_success_rate": f"{(db.session.query(DocumentLog).filter_by(extraction_status=ExtractionStatus.SUCCESS).count() / db.session.query(DocumentLog).count() * 100) if db.session.query(DocumentLog).count() > 0 else 0:.1f}%",
            "token_stats": {
                "total_tokens": total_tokens,
                "total_prompt_tokens": total_prompt_tokens,
                "total_candidates_tokens": total_candidates_tokens,
                "total_cached_tokens": total_cached_tokens,
                "total_non_cached_prompt_tokens": total_non_cached_prompt_tokens,
            },
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching dashboard stats: {e}")
        # Return empty/default stats on error
        return {
            "reports_generated": "N/A",
            "api_cost_monthly_est": "$0.00",
            "avg_generation_time_secs": "N/A",
            "processing_errors": "N/A",
            "total_documents": "N/A",
            "extraction_success_rate": "N/A",
            "token_stats": {
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_candidates_tokens": 0,
                "total_cached_tokens": 0,
                "total_non_cached_prompt_tokens": 0,
            },
        }


def get_system_status() -> Dict[str, str]:
    """
    Checks the status of system components.
    """
    status = {
        "database": "unknown",
        "redis": "unknown",
        "llm_api": "unknown",
    }

    # Check Database
    try:
        db.session.execute(text("SELECT 1"))
        status["database"] = "operational"
    except Exception:
        status["database"] = "error"

    # Check Redis
    try:
        # Simple check: try to get a connection from the pool
        # Note: This might not actually ping Redis unless we execute a command
        # But for now, let's assume if we can import and it doesn't crash, it's okay-ish
        # A real ping would be better but requires a redis client instance.
        # Let's try to create a strict redis client from the config URL
        import redis

        from core.config import settings

        r = redis.from_url(settings.REDIS_URL)
        if r.ping():
            status["redis"] = "operational"
        else:
            status["redis"] = "error"
    except Exception:
        status["redis"] = "error"

    # Check LLM API Key
    from core.config import settings

    if settings.GEMINI_API_KEY:
        status["llm_api"] = "configured"
    else:
        status["llm_api"] = "missing_key"

    return status
