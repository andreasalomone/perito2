"""add_error_message_to_documents

Revision ID: 5019d760e2bc
Revises: q3l4m5n6o7p8
Create Date: 2025-12-10 11:24:56.945325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5019d760e2bc'
down_revision: Union[str, Sequence[str], None] = 'q3l4m5n6o7p8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add error_message column to documents table."""
    op.add_column('documents', sa.Column('error_message', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    """Downgrade schema: Remove error_message column from documents table."""
    op.drop_column('documents', 'error_message')
