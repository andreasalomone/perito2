"""Widen template_used column to VARCHAR(64)

Revision ID: z3a4b5c6d7e8
Revises: z2a3b4c5d6e7
Create Date: 2025-12-17

Fixes: 422 errors on preliminary report streaming due to
inserting 64-character SHA256 hashes into VARCHAR(20) column.
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'z3a4b5c6d7e8'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('report_versions', 'template_used',
                    type_=sa.String(64),
                    existing_type=sa.String(20),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('report_versions', 'template_used',
                    type_=sa.String(20),
                    existing_type=sa.String(64),
                    existing_nullable=True)
