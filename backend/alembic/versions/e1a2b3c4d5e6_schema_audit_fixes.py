"""Schema audit fixes

Revision ID: e1a2b3c4d5e6
Revises: d8f9e0d1a2b3
Create Date: 2025-12-03 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'd8f9e0d1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Fix Nullability on State Columns
    # cases.status
    op.execute("UPDATE cases SET status = 'OPEN' WHERE status IS NULL")
    op.alter_column('cases', 'status',
               existing_type=sa.VARCHAR(length=50),
               nullable=False,
               server_default='OPEN')

    # documents.ai_status
    op.execute("UPDATE documents SET ai_status = 'PENDING' WHERE ai_status IS NULL")
    op.alter_column('documents', 'ai_status',
               existing_type=sa.VARCHAR(length=50),
               nullable=False,
               server_default='PENDING')

    # report_versions.is_final
    op.execute("UPDATE report_versions SET is_final = false WHERE is_final IS NULL")
    op.alter_column('report_versions', 'is_final',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               server_default=sa.text('false'))

    # 2. Enforce User Email Uniqueness
    op.create_unique_constraint('users_email_key', 'users', ['email'])

    # 3. Add Missing Indexes for Performance
    op.create_index('idx_audit_logs_org_created', 'audit_logs', ['organization_id', sa.text('created_at DESC')])
    op.create_index('idx_audit_logs_user', 'audit_logs', ['user_id'])

    # 4. Prevent Version Conflicts
    op.create_unique_constraint('uq_report_versions_case_ver', 'report_versions', ['case_id', 'version_number'])


def downgrade() -> None:
    # 4. Prevent Version Conflicts
    op.drop_constraint('uq_report_versions_case_ver', 'report_versions', type_='unique')

    # 3. Add Missing Indexes for Performance
    op.drop_index('idx_audit_logs_user', table_name='audit_logs')
    op.drop_index('idx_audit_logs_org_created', table_name='audit_logs')

    # 2. Enforce User Email Uniqueness
    op.drop_constraint('users_email_key', 'users', type_='unique')

    # 1. Fix Nullability on State Columns
    # report_versions.is_final
    op.alter_column('report_versions', 'is_final',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               server_default=None)

    # documents.ai_status
    op.alter_column('documents', 'ai_status',
               existing_type=sa.VARCHAR(length=50),
               nullable=True,
               server_default=None)

    # cases.status
    op.alter_column('cases', 'status',
               existing_type=sa.VARCHAR(length=50),
               nullable=True,
               server_default=None)
