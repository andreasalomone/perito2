"""Fix orphaned finalized cases - set status to CLOSED

Revision ID: q3l4m5n6o7p8
Revises: edcbbd314a30
Create Date: 2025-12-08

This migration fixes cases that have is_final=true on a report_version
but status was never set to CLOSED due to a bug in finalize_case().
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'q3l4m5n6o7p8'
down_revision = 'edcbbd314a30'  # Points to the merge head
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix orphaned finalized cases by setting their status to 'CLOSED'.
    
    These cases have:
    - A report_version with is_final = true
    - Case status != 'CLOSED' (usually 'OPEN')
    
    This is a data-only migration, no schema changes.
    """
    # Use raw SQL for efficiency and to avoid ORM complexity
    op.execute("""
        UPDATE cases
        SET status = 'CLOSED'
        WHERE id IN (
            SELECT DISTINCT c.id
            FROM cases c
            INNER JOIN report_versions rv ON rv.case_id = c.id
            WHERE rv.is_final = true
            AND c.status != 'CLOSED'
            AND c.deleted_at IS NULL
        )
    """)


def downgrade() -> None:
    """
    Revert orphaned finalized cases back to 'OPEN'.
    
    Note: This assumes all affected cases were previously 'OPEN',
    which is the expected state given the bug we're fixing.
    Use with caution in production.
    """
    op.execute("""
        UPDATE cases
        SET status = 'OPEN'
        WHERE id IN (
            SELECT DISTINCT c.id
            FROM cases c
            INNER JOIN report_versions rv ON rv.case_id = c.id
            WHERE rv.is_final = true
            AND c.status = 'CLOSED'
            AND c.deleted_at IS NULL
        )
    """)
