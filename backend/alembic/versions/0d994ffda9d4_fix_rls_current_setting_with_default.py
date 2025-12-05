"""fix_rls_current_setting_with_default

Revision ID: 0d994ffda9d4
Revises: 4edd7831e942
Create Date: 2025-12-05 14:06:15.927931

Fix RLS policies to use current_setting with missing_ok=true parameter.
This prevents "unrecognized configuration parameter" errors when the
app.current_org_id session variable hasn't been set yet.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d994ffda9d4'
down_revision: Union[str, None] = 'ef962812a799'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Update RLS policies to use current_setting('app.current_org_id', true).
    The second parameter (true) makes current_setting return NULL instead of
    throwing an error when the parameter doesn't exist.
    """
    # Drop existing policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON cases;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON report_versions;")
    
    # Recreate with fixed current_setting calls
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON cases
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON clients
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON documents
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON report_versions
        FOR ALL
        USING (organization_id = (current_setting('app.current_org_id', true))::uuid);
    """)


def downgrade() -> None:
    """
    Rollback to policies without the missing_ok parameter.
    """
    # Drop fixed policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON cases;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON report_versions;")
    
    # Recreate old broken policies (without missing_ok)
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
