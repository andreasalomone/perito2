"""Add database indexes and unique constraint for performance and data integrity

Revision ID: x0s2t3u4v5w6
Revises: w9r1s2t3u4v5
Create Date: 2025-12-15

Fixes:
- Add idx_cases_org_status for status filtering
- Add idx_clients_name_trgm for text search (pg_trgm)
- Add unique constraint on documents(case_id, filename) to prevent duplicates
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "x0s2t3u4v5w6"
down_revision = "w9r1s2t3u4v5"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Status filter index (partial index for active cases only)
    # NOTE: postgresql_where requires a SQLAlchemy expression (sa.text), not a plain string
    # Using if_not_exists=True for idempotency - safe to re-run
    op.create_index(
        "idx_cases_org_status",
        "cases",
        ["organization_id", "status"],
        postgresql_where=sa.text("status != 'ARCHIVED' AND deleted_at IS NULL"),
        if_not_exists=True,
    )

    # 2. Trigram index for client name search (requires pg_trgm extension)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_clients_name_trgm
        ON clients USING gin (name gin_trgm_ops)
    """)

    # 3. De-duplicate existing documents before adding constraint
    # This renames duplicate filenames by appending their row number
    op.execute("""
        UPDATE documents
        SET filename = filename || '_' || sub.rn
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY case_id, filename ORDER BY created_at) AS rn
            FROM documents
        ) sub
        WHERE documents.id = sub.id
          AND sub.rn > 1
    """)

    # 4. Unique constraint to prevent duplicate filenames per case
    # Check if constraint exists before creating (make idempotent)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_documents_case_filename'
            ) THEN
                ALTER TABLE documents ADD CONSTRAINT uq_documents_case_filename
                UNIQUE (case_id, filename);
            END IF;
        END
        $$;
    """)


def downgrade():
    op.drop_constraint("uq_documents_case_filename", "documents", type_="unique")
    op.execute("DROP INDEX IF EXISTS idx_clients_name_trgm")
    op.drop_index("idx_cases_org_status", table_name="cases")
