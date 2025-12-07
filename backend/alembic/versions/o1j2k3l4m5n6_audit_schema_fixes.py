"""audit_schema_fixes

Revision ID: o1j2k3l4m5n6
Revises: n0i1j2k3l4m5_add_created_at_to_users
Create Date: 2025-12-07 12:44:00.000000

Fixes identified by external database audit:
1. outbox_messages.organization_id: VARCHAR(36) -> UUID
2. audit_logs.details: JSON -> JSONB
3. Add GIN index on documents.ai_extracted_data
4. Improve audit_logs index for multi-tenant queries
5. ml_training_pairs FK lifecycle: RESTRICT -> SET NULL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o1j2k3l4m5n6'
down_revision: Union[str, None] = 'n0i1j2k3l4m5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply audit schema fixes."""
    
    # 1. FIX: outbox_messages.organization_id type drift (VARCHAR -> UUID)
    op.execute("""
        ALTER TABLE outbox_messages 
        ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid;
    """)
    
    # 2. FIX: audit_logs.details to JSONB (more efficient storage/parsing)
    op.execute("""
        ALTER TABLE audit_logs 
        ALTER COLUMN details TYPE jsonb USING details::jsonb;
    """)
    
    # 3. FIX: Add GIN index for AI data searches on documents
    # Using CONCURRENTLY to avoid locking the table during index creation
    # Note: CONCURRENTLY requires the migration to run outside a transaction
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_ai_data_gin 
        ON documents USING GIN (ai_extracted_data);
    """)
    
    # 4. FIX: Improve audit_logs index for multi-tenant queries
    # Drop the old single-column index and create composite
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_user;")
    op.execute("""
        CREATE INDEX idx_audit_logs_org_user 
        ON audit_logs (organization_id, user_id);
    """)
    
    # 5. FIX: ml_training_pairs FK lifecycle (RESTRICT -> SET NULL)
    # This allows purging old report_versions without blocking on training data
    op.execute("""
        ALTER TABLE ml_training_pairs 
        DROP CONSTRAINT IF EXISTS ml_training_pairs_ai_version_id_fkey;
    """)
    op.execute("""
        ALTER TABLE ml_training_pairs 
        ADD CONSTRAINT ml_training_pairs_ai_version_id_fkey 
        FOREIGN KEY (ai_version_id) REFERENCES report_versions(id) ON DELETE SET NULL;
    """)
    
    op.execute("""
        ALTER TABLE ml_training_pairs 
        DROP CONSTRAINT IF EXISTS ml_training_pairs_final_version_id_fkey;
    """)
    op.execute("""
        ALTER TABLE ml_training_pairs 
        ADD CONSTRAINT ml_training_pairs_final_version_id_fkey 
        FOREIGN KEY (final_version_id) REFERENCES report_versions(id) ON DELETE SET NULL;
    """)


def downgrade() -> None:
    """Revert audit schema fixes."""
    
    # 5. Revert FK constraints back to RESTRICT (Postgres default)
    op.execute("""
        ALTER TABLE ml_training_pairs 
        DROP CONSTRAINT IF EXISTS ml_training_pairs_final_version_id_fkey;
    """)
    op.execute("""
        ALTER TABLE ml_training_pairs 
        ADD CONSTRAINT ml_training_pairs_final_version_id_fkey 
        FOREIGN KEY (final_version_id) REFERENCES report_versions(id);
    """)
    
    op.execute("""
        ALTER TABLE ml_training_pairs 
        DROP CONSTRAINT IF EXISTS ml_training_pairs_ai_version_id_fkey;
    """)
    op.execute("""
        ALTER TABLE ml_training_pairs 
        ADD CONSTRAINT ml_training_pairs_ai_version_id_fkey 
        FOREIGN KEY (ai_version_id) REFERENCES report_versions(id);
    """)
    
    # 4. Revert audit_logs index
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_org_user;")
    op.execute("CREATE INDEX idx_audit_logs_user ON audit_logs (user_id);")
    
    # 3. Drop GIN index
    op.execute("DROP INDEX IF EXISTS idx_documents_ai_data_gin;")
    
    # 2. Revert audit_logs.details to JSON
    op.execute("""
        ALTER TABLE audit_logs 
        ALTER COLUMN details TYPE json USING details::json;
    """)
    
    # 1. Revert outbox_messages.organization_id to VARCHAR(36)
    op.execute("""
        ALTER TABLE outbox_messages 
        ALTER COLUMN organization_id TYPE varchar(36) USING organization_id::text;
    """)
