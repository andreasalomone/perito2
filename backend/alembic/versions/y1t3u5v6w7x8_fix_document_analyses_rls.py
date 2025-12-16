"""Fix insecure RLS policy on document_analyses table

The original policy used COALESCE fallback which allowed all rows to be
returned when app.current_org_id was not set. This was a critical security
vulnerability that could leak data across organizations.

This migration replaces it with a strict policy that returns NO rows when
the RLS context is not set, matching the secure pattern used on other tables.

Revision ID: y1t3u5v6w7x8
Revises: x0s2t3u4v5w6
Create Date: 2025-12-16
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'y1t3u5v6w7x8'
down_revision: Union[str, None] = 'x0s2t3u4v5w6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the insecure policy that uses COALESCE fallback
    op.execute("""
        DROP POLICY IF EXISTS document_analyses_tenant_isolation ON document_analyses
    """)

    # 2. Create secure policy matching the pattern used for cases/clients/documents
    # Key difference: No COALESCE fallback. If app.current_org_id is not set,
    # NULLIF returns NULL and the comparison fails, returning NO rows.
    op.execute("""
        CREATE POLICY document_analyses_tenant_isolation
        ON document_analyses
        FOR ALL
        TO PUBLIC
        USING (
            organization_id = (
                NULLIF(current_setting('app.current_org_id', true), '')
            )::uuid
        )
        WITH CHECK (
            organization_id = (
                NULLIF(current_setting('app.current_org_id', true), '')
            )::uuid
        )
    """)


def downgrade() -> None:
    # Restore the original (insecure) policy for rollback
    # WARNING: This reintroduces the security vulnerability
    op.execute("""
        DROP POLICY IF EXISTS document_analyses_tenant_isolation ON document_analyses
    """)

    op.execute("""
        CREATE POLICY document_analyses_tenant_isolation
        ON document_analyses
        FOR ALL
        TO PUBLIC
        USING (organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', true), '')::uuid,
            organization_id
        ))
    """)
