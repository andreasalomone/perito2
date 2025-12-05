"""add_composite_fk_documents_case_org

Revision ID: j6e7f8g9h0i1
Revises: 0d994ffda9d4
Create Date: 2025-12-05 15:48:00.000000

Add composite foreign key to enforce document.organization_id == case.organization_id
at the database level. This provides defense-in-depth against application bugs that
might create documents with mismatched organization IDs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j6e7f8g9h0i1'
down_revision: Union[str, None] = '0d994ffda9d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add composite unique constraint to cases table and composite foreign key
    to documents table to enforce organizational consistency.
    """
    # Step 1: Add unique constraint on cases (id, organization_id)
    # This is required before we can reference both columns as a foreign key
    op.create_unique_constraint(
        'uq_cases_id_org',
        'cases',
        ['id', 'organization_id']
    )
    
    # Step 2: Drop the existing simple foreign key on documents.case_id
    op.drop_constraint('documents_case_id_fkey', 'documents', type_='foreignkey')
    
    # Step 3: Create the new composite foreign key
    # This enforces that documents can only reference cases where BOTH
    # case_id matches AND organization_id matches
    op.create_foreign_key(
        'documents_case_org_fkey',
        'documents',
        'cases',
        ['case_id', 'organization_id'],
        ['id', 'organization_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """
    Rollback to simple foreign key without organizational constraint.
    """
    # Step 1: Drop the composite foreign key
    op.drop_constraint('documents_case_org_fkey', 'documents', type_='foreignkey')
    
    # Step 2: Recreate the original simple foreign key on case_id only
    op.create_foreign_key(
        'documents_case_id_fkey',
        'documents',
        'cases',
        ['case_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Step 3: Drop the unique constraint on cases
    op.drop_constraint('uq_cases_id_org', 'cases', type_='unique')
