"""Add created_at to users table

Revision ID: n0i1j2k3l4m5
Revises: m9h0i1j2k3l4
Create Date: 2025-12-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'n0i1j2k3l4m5'
down_revision: Union[str, Sequence[str], None] = 'm9h0i1j2k3l4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), 
                   server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'created_at')
