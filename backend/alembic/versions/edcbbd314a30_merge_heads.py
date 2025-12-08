"""merge_heads

Revision ID: edcbbd314a30
Revises: a3b4c5d6e7f8, p2k3l4m5n6o7
Create Date: 2025-12-08 10:59:54.781855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'edcbbd314a30'
down_revision: Union[str, Sequence[str], None] = ('a3b4c5d6e7f8', 'p2k3l4m5n6o7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
