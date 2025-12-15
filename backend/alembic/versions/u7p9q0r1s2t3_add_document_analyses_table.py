"""Add document_analyses table for Early Analysis feature

Creates the document_analyses table to store AI-generated document analysis
results with staleness tracking via document_hash.

NOTE: Foreign keys are NOT created in this migration due to permission requirements.
Run these SQL statements manually as postgres after migration:

    ALTER TABLE document_analyses
    ADD CONSTRAINT fk_document_analyses_case
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;

    ALTER TABLE document_analyses
    ADD CONSTRAINT fk_document_analyses_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);

Revision ID: u7p9q0r1s2t3
Revises: t6o8p9q0r1s2
Create Date: 2025-12-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'u7p9q0r1s2t3'
down_revision: Union[str, None] = 't6o8p9q0r1s2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create document_analyses table WITHOUT foreign key constraints
    # FKs require REFERENCES permission which the migration user may not have
    op.create_table(
        'document_analyses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('case_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('received_docs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('missing_docs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('document_hash', sa.String(length=64), nullable=False),
        sa.Column('is_stale', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient querying
    op.create_index('idx_document_analyses_case', 'document_analyses', ['case_id'])
    op.create_index('idx_document_analyses_org', 'document_analyses', ['organization_id'])

    # Enable RLS on the new table
    op.execute("ALTER TABLE document_analyses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_analyses FORCE ROW LEVEL SECURITY")

    # Create RLS policy - same pattern as other tables
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


def downgrade() -> None:
    # Drop RLS policy first
    op.execute("DROP POLICY IF EXISTS document_analyses_tenant_isolation ON document_analyses")

    # Drop foreign keys if they exist (may have been added manually)
    op.execute("ALTER TABLE document_analyses DROP CONSTRAINT IF EXISTS fk_document_analyses_case")
    op.execute("ALTER TABLE document_analyses DROP CONSTRAINT IF EXISTS fk_document_analyses_org")

    # Drop indexes
    op.drop_index('idx_document_analyses_org', table_name='document_analyses')
    op.drop_index('idx_document_analyses_case', table_name='document_analyses')

    # Drop table
    op.drop_table('document_analyses')
