"""force_rls_for_table_owners

Revision ID: ef962812a799
Revises: 4edd7831e942
Create Date: 2025-12-05 11:42:15.567016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef962812a799'
down_revision: Union[str, Sequence[str], None] = '4edd7831e942'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable FORCE ROW LEVEL SECURITY to apply RLS policies to table owners.
    
    By default, RLS policies don't apply to table owners.
    FORCE ROW LEVEL SECURITY makes them apply to everyone, including owners.
    
    This is the CRITICAL fix for the multi-tenancy bug.
    """
    # Enable FORCE ROW LEVEL SECURITY on all tables
    op.execute("ALTER TABLE cases FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE report_versions FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    """
    Rollback: Disable FORCE ROW LEVEL SECURITY.
    """
    # Disable FORCE ROW LEVEL SECURITY (back to default - owners bypass RLS)
    op.execute("ALTER TABLE cases NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE clients NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE documents NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE report_versions NO FORCE ROW LEVEL SECURITY;")
