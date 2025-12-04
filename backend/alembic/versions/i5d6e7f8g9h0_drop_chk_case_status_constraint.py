"""drop_chk_case_status_constraint

The casestatus ENUM type already enforces valid values (OPEN, CLOSED, ARCHIVED,
GENERATING, PROCESSING, ERROR). The CHECK constraint incorrectly limits to only
OPEN/CLOSED/ARCHIVED, blocking the report generation pipeline.

Revision ID: i5d6e7f8g9h0
Revises: h4c5d6e7f8g9
Create Date: 2025-12-04 22:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'i5d6e7f8g9h0'
down_revision: Union[str, Sequence[str], None] = 'h4c5d6e7f8g9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the obsolete CHECK constraint that only allows OPEN/CLOSED/ARCHIVED.
    # The casestatus ENUM type enforces valid values at the database level.
    op.drop_constraint('chk_case_status', 'cases', type_='check')


def downgrade() -> None:
    # WARNING: Re-adding this constraint will break the application.
    # Only downgrade if you're sure no cases have GENERATING/PROCESSING/ERROR status.
    op.create_check_constraint(
        'chk_case_status',
        'cases',
        sa.text("status::text = ANY(ARRAY['OPEN'::varchar, 'CLOSED'::varchar, 'ARCHIVED'::varchar]::text[])")
    )
