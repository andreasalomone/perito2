"""merge_google_docs_branch

Revision ID: 9d8030865527
Revises: 5019d760e2bc, r4m5n6o7p8q9
Create Date: 2025-12-10 13:41:21.964625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d8030865527'
down_revision: Union[str, Sequence[str], None] = ('5019d760e2bc', 'r4m5n6o7p8q9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
