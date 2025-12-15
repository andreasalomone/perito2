"""Add source column to report_versions for distinguishing preliminary from final

Revision ID: v8q0r1s2t3u4
Revises: u7p9q0r1s2t3
Create Date: 2025-12-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'v8q0r1s2t3u4'
down_revision: Union[str, None] = 'u7p9q0r1s2t3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source column to distinguish preliminary from final reports
    # Values: 'preliminary', 'final', or NULL (legacy)
    op.add_column(
        'report_versions',
        sa.Column('source', sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('report_versions', 'source')
