"""Add database indexes and unique constraint for performance and data integrity

Revision ID: x0s2t3u4v5w6
Revises: w9r1s2t3u4v5
Create Date: 2025-12-15

Fixes:
- Add idx_cases_org_status for status filtering
- Add idx_clients_name_trgm for text search (pg_trgm)
- Add unique constraint on documents(case_id, filename) to prevent duplicates
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "x0s2t3u4v5w6"
down_revision = "w9r1s2t3u4v5"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Status filter index (partial index for active cases only)
    op.create_index(
        "idx_cases_org_status",
        "cases",
        ["organization_id", "status"],
        postgresql_where="status != 'ARCHIVED' AND deleted_at IS NULL",
    )

    # 2. Trigram index for client name search (requires pg_trgm extension)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX idx_clients_name_trgm
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
    op.create_unique_constraint(
        "uq_documents_case_filename",
        "documents",
        ["case_id", "filename"],
    )


def downgrade():
    op.drop_constraint("uq_documents_case_filename", "documents", type_="unique")
    op.execute("DROP INDEX IF EXISTS idx_clients_name_trgm")
    op.drop_index("idx_cases_org_status", table_name="cases")
