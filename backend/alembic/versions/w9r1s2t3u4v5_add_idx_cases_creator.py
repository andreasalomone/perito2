"""Add idx_cases_creator index for My Cases filter

Revision ID: w9r1s2t3u4v5
Revises: v8q0r1s2t3u4
Create Date: 2025-12-15

Fixes P1: Missing index for scope=mine filter causes sequential scan on creator_id.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "w9r1s2t3u4v5"
down_revision = "v8q0r1s2t3u4"
branch_labels = None
depends_on = None


def upgrade():
    # Add composite index for "My Cases" filter (scope=mine)
    # Note: Not using CONCURRENTLY as Alembic runs in transaction mode
    op.create_index(
        "idx_cases_creator",
        "cases",
        ["organization_id", "creator_id", "created_at"],
        postgresql_where="deleted_at IS NULL",
    )


def downgrade():
    op.drop_index("idx_cases_creator", table_name="cases")
