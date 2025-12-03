"""audit_fixes

Revision ID: 9db07502eeea
Revises: f2a3b4c5d6e7
Create Date: 2025-12-03 20:05:25.728698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9db07502eeea'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    -- 1. FIX TIMEZONES
    ALTER TABLE cases ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    ALTER TABLE documents ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    ALTER TABLE audit_logs ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    ALTER TABLE outbox_messages ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    ALTER TABLE outbox_messages ALTER COLUMN processed_at TYPE timestamptz USING processed_at AT TIME ZONE 'UTC';

    -- 2. ENFORCE ENUMS
    -- Pre-process data to match Enum values (Uppercase)
    UPDATE users SET role = UPPER(role);
    UPDATE documents SET ai_status = UPPER(ai_status);

    -- Drop defaults first to avoid casting errors
    ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
    ALTER TABLE documents ALTER COLUMN ai_status DROP DEFAULT;

    -- Users
    ALTER TABLE users 
        ALTER COLUMN role TYPE userrole USING role::userrole,
        ALTER COLUMN role SET DEFAULT 'MEMBER',
        ALTER COLUMN role SET NOT NULL;

    -- Cases
    ALTER TABLE cases 
        ADD CONSTRAINT chk_case_status CHECK (status IN ('OPEN', 'CLOSED', 'ARCHIVED')); 

    -- Documents
    ALTER TABLE documents
        ALTER COLUMN ai_status TYPE extractionstatus USING ai_status::extractionstatus,
        ALTER COLUMN ai_status SET DEFAULT 'PROCESSING';

    -- 3. FIX AUDIT LOGS DELETION
    ALTER TABLE audit_logs DROP CONSTRAINT audit_logs_user_id_fkey;
    ALTER TABLE audit_logs 
        ADD CONSTRAINT audit_logs_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

    -- 4. OPTIMIZE OUTBOX MESSAGES
    ALTER TABLE outbox_messages ALTER COLUMN payload TYPE jsonb USING payload::jsonb;
    ALTER TABLE outbox_messages ALTER COLUMN status SET DEFAULT 'PENDING';
    ALTER TABLE outbox_messages ALTER COLUMN status SET NOT NULL;

    CREATE INDEX idx_outbox_pending 
        ON outbox_messages (created_at) 
        WHERE status = 'PENDING';
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    -- Revert Outbox
    DROP INDEX idx_outbox_pending;
    ALTER TABLE outbox_messages ALTER COLUMN payload TYPE json USING payload::json;
    
    -- Revert Audit Logs
    ALTER TABLE audit_logs DROP CONSTRAINT audit_logs_user_id_fkey;
    ALTER TABLE audit_logs 
        ADD CONSTRAINT audit_logs_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id);

    -- Revert Enums (Relax constraints)
    ALTER TABLE cases DROP CONSTRAINT chk_case_status;
    ALTER TABLE users ALTER COLUMN role TYPE varchar USING role::varchar;
    ALTER TABLE documents ALTER COLUMN ai_status TYPE varchar USING ai_status::varchar;

    -- Revert Timezones
    ALTER TABLE cases ALTER COLUMN created_at TYPE timestamp;
    ALTER TABLE documents ALTER COLUMN created_at TYPE timestamp;
    ALTER TABLE audit_logs ALTER COLUMN created_at TYPE timestamp;
    ALTER TABLE outbox_messages ALTER COLUMN created_at TYPE timestamp;
    ALTER TABLE outbox_messages ALTER COLUMN processed_at TYPE timestamp;
    """)
