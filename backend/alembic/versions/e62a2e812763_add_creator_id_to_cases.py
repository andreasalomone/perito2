"""add_creator_id_to_cases

Revision ID: e62a2e812763
Revises: j6e7f8g9h0i1
Create Date: 2025-12-05 17:31:40.424770

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e62a2e812763'
down_revision: Union[str, Sequence[str], None] = 'j6e7f8g9h0i1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('cases', sa.Column('creator_id', sa.String(128), nullable=True))
    op.create_foreign_key('fk_cases_creator_id_users', 'cases', 'users', ['creator_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_cases_creator_id_users', 'cases', type_='foreignkey')
    op.drop_column('cases', 'creator_id')
