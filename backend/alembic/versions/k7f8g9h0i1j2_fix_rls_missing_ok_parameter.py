"""fix_rls_missing_ok_parameter

Revision ID: k7f8g9h0i1j2
Revises: j6e7f8g9h0i1_add_composite_fk_documents_case_org
Create Date: 2025-12-06 11:00:00.000000

FIX: The migration 4edd7831e942 removed the missing_ok=true parameter
from current_setting() calls in RLS policies. This causes errors when 
db.refresh() is called after db.commit() because the session variable
might not be visible to the new implicit transaction.

This migration re-adds the missing_ok=true parameter (second argument)
which makes current_setting() return NULL instead of throwing an error
when the variable is not set.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'k7f8g9h0i1j2'
down_revision: Union[str, Sequence[str], None] = 'e62a2e812763'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix RLS policies by adding missing_ok=true parameter to current_setting().
    
    This prevents errors when the session variable is not set, returning NULL instead.
    Combined with FOR ALL, this ensures proper RLS enforcement for all operations.
    """
    # Drop existing policies (they're missing missing_ok parameter)
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON cases;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON report_versions;")
    
    # Recreate with FOR ALL clause AND missing_ok=true parameter
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON cases
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid)
        WITH CHECK (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON clients
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid)
        WITH CHECK (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON documents
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid)
        WITH CHECK (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON report_versions
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid)
        WITH CHECK (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)


def downgrade() -> None:
    """
    Rollback: Drop the fixed policies and recreate the broken ones (without missing_ok).
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON cases;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON report_versions;")
    
    # Recreate old policies (without missing_ok - the broken version from 4edd7831e942)
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
