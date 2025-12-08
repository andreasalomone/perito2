"""Add ai_summary to cases

Revision ID: p2k3l4m5n6o7
Revises: o1j2k3l4m5n6
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p2k3l4m5n6o7'
down_revision = 'o1j2k3l4m5n6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ai_summary column to cases table."""
    op.add_column('cases', sa.Column('ai_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove ai_summary column from cases table."""
    op.drop_column('cases', 'ai_summary')
