"""Add document_hash column to report_versions

Revision ID: a4b5c6d7e8f9
Revises: z3a4b5c6d7e8
Create Date: 2025-12-18

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a4b5c6d7e8f9'
down_revision = 'z3a4b5c6d7e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add document_hash column
    op.add_column('report_versions', sa.Column('document_hash', sa.String(length=64), nullable=True))

    # 2. Data migration: copy hashes from template_used for preliminary reports
    op.execute(
        "UPDATE report_versions SET document_hash = template_used WHERE source = 'preliminary'"
    )

    # 3. Clean up old workaround data
    op.execute(
        "UPDATE report_versions SET template_used = NULL WHERE source = 'preliminary'"
    )


def downgrade() -> None:
    # Reverse data migration: copy back to template_used if it was a preliminary report
    op.execute(
        "UPDATE report_versions SET template_used = document_hash WHERE source = 'preliminary' AND template_used IS NULL"
    )

    # Remove document_hash column
    op.drop_column('report_versions', 'document_hash')
