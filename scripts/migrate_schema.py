import logging
import os
import sys

# Add the parent directory to sys.path to allow imports from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app import app  # noqa: E402
from core.database import db  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_schema():
    """
    Manually adds missing columns to the database tables.
    This is a temporary solution since we don't have a migration tool like Alembic yet.
    """
    with app.app_context():
        logger.info("Starting schema migration...")

        try:
            # ReportLog updates
            logger.info("Checking ReportLog table...")
            with db.engine.connect() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE report_log ADD COLUMN IF NOT EXISTS llm_raw_response TEXT;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE report_log ADD COLUMN IF NOT EXISTS final_report_text TEXT;"
                    )
                )
                conn.commit()
            logger.info("ReportLog table updated.")

            # DocumentLog updates
            logger.info("Checking DocumentLog table...")
            with db.engine.connect() as conn:
                # For ENUMs in Postgres, we might need to handle them carefully.
                # For simplicity, we'll add extraction_status as VARCHAR first if it doesn't exist.
                # If using SQLAlchemy Enum, it maps to VARCHAR by default in some setups or a custom type.
                # Let's try adding as VARCHAR to be safe, or check if we can use the Enum type.
                # Given the error is likely missing column, let's add it.

                # Note: If extractionstatus enum type exists, we might need to use it.
                # But 'text' or 'varchar' is safer for a quick fix.
                conn.execute(
                    text(
                        "ALTER TABLE document_log ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(50);"
                    )
                )

                conn.execute(
                    text(
                        "ALTER TABLE document_log ADD COLUMN IF NOT EXISTS extracted_content_length INTEGER DEFAULT 0;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE document_log ADD COLUMN IF NOT EXISTS error_message TEXT;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE document_log ADD COLUMN IF NOT EXISTS file_type VARCHAR(50);"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE document_log ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(50);"
                    )
                )
                conn.commit()
            logger.info("DocumentLog table updated.")

            logger.info("Schema migration completed successfully.")

        except Exception as e:
            logger.error(f"Error during migration: {e}")
            sys.exit(1)


if __name__ == "__main__":
    migrate_schema()
