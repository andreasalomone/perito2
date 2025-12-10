"""Add Google Docs draft columns to report_versions

Revision ID: r4m5n6o7p8q9
Revises: q3l4m5n6o7p8
Create Date: 2025-12-10

Adds columns to support Google Docs Live Draft editing:
- google_doc_id: Stores the Google Drive file ID
- is_draft_active: Boolean flag for active draft sessions
- edit_link: Direct URL to the Google Doc
- template_used: Which template (bn/salomone) was used to generate
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r4m5n6o7p8q9'
down_revision = 'q3l4m5n6o7p8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('report_versions', sa.Column('google_doc_id', sa.String(255), nullable=True))
    op.add_column('report_versions', sa.Column('is_draft_active', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('report_versions', sa.Column('edit_link', sa.String(1024), nullable=True))
    op.add_column('report_versions', sa.Column('template_used', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('report_versions', 'template_used')
    op.drop_column('report_versions', 'edit_link')
    op.drop_column('report_versions', 'is_draft_active')
    op.drop_column('report_versions', 'google_doc_id')
