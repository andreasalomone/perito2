"""add_for_all_to_rls_policies

Revision ID: 4edd7831e942
Revises: i5d6e7f8g9h0
Create Date: 2025-12-05 11:27:49.330311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4edd7831e942'
down_revision: Union[str, Sequence[str], None] = 'i5d6e7f8g9h0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix RLS policies by adding FOR ALL clause.
    
    Without FOR ALL, policies only apply to table owners.
    With FOR ALL, policies apply to all roles including report_user.
    """
    # Drop existing policies (they're insufficient - missing FOR ALL)
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON cases;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON report_versions;")
    
    # Recreate with FOR ALL clause
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON cases
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON clients
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON documents
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON report_versions
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)


def downgrade() -> None:
    """
    Rollback: Drop the FOR ALL policies and recreate the old ones.
    """
    # Drop FOR ALL policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON cases;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON report_versions;")
    
    # Recreate old policies (without FOR ALL - the broken version)
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON cases
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON clients
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON documents
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON report_versions
        USING (organization_id = (current_setting('app.current_org_id'))::uuid);
    """)
