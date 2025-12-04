"""add_outbox_organization_id

Revision ID: h4c5d6e7f8g9
Revises: g3b4c5d6e7f8
Create Date: 2025-12-04 19:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'h4c5d6e7f8g9'
down_revision: Union[str, Sequence[str], None] = '20fc7bb876cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add organization_id column for tenant isolation (nullable for backward compat)
    op.add_column('outbox_messages', sa.Column('organization_id', sa.String(36), nullable=True))
    
    # Add index for efficient tenant-scoped FIFO queries
    op.create_index(
        'idx_outbox_org_pending', 
        'outbox_messages', 
        ['organization_id', 'created_at'],
        postgresql_where=sa.text("status = 'PENDING'")
    )


def downgrade() -> None:
    op.drop_index('idx_outbox_org_pending', table_name='outbox_messages')
    op.drop_column('outbox_messages', 'organization_id')
