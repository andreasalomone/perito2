"""add_deleted_at_to_cases

Revision ID: l8g9h0i1j2k3
Revises: k7f8g9h0i1j2
Create Date: 2025-12-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l8g9h0i1j2k3'
down_revision: Union[str, Sequence[str], None] = 'k7f8g9h0i1j2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add deleted_at column to cases table
    op.add_column('cases', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Drop deleted_at column from cases table
    op.drop_column('cases', 'deleted_at')
