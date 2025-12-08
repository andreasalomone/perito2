"""Add email intake tables

Revision ID: a3b4c5d6e7f8
Revises: 2e94a38ba2fd
Create Date: 2025-12-08 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = '2e94a38ba2fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email intake tables for Brevo integration."""
    
    # -------------------------------------------------------------------------
    # 1. email_processing_log - tracks all emails received
    # -------------------------------------------------------------------------
    op.create_table(
        'email_processing_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('user_id', sa.String(128), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('case_id', UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='SET NULL'), nullable=True),
        
        # Email metadata
        sa.Column('webhook_id', sa.String(255), nullable=False, unique=True),
        sa.Column('sender_email', sa.String(255), nullable=False),
        sa.Column('sender_name', sa.String(255), nullable=True),
        sa.Column('subject', sa.String(1024), nullable=True),
        sa.Column('message_id', sa.String(255), nullable=True),
        
        # Processing status: 'received', 'authorized', 'unauthorized', 'processed', 'failed'
        sa.Column('status', sa.String(50), nullable=False, server_default='received'),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Counts
        sa.Column('attachment_count', sa.Integer(), server_default='0'),
        sa.Column('documents_created', sa.Integer(), server_default='0'),
        
        # Timestamps
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for email_processing_log
    op.create_index('idx_email_log_org_received', 'email_processing_log', ['organization_id', sa.text('received_at DESC')])
    op.create_index('idx_email_log_status', 'email_processing_log', ['status'])
    op.create_index('idx_email_log_sender', 'email_processing_log', ['sender_email'])
    
    # -------------------------------------------------------------------------
    # 2. email_attachments - tracks attachments downloaded from emails
    # -------------------------------------------------------------------------
    op.create_table(
        'email_attachments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email_log_id', UUID(as_uuid=True), sa.ForeignKey('email_processing_log.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        
        # Attachment metadata
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        
        # Storage - matches documents.gcs_path format
        sa.Column('gcs_path', sa.String(1024), nullable=True),
        sa.Column('brevo_download_url', sa.String(2048), nullable=True),
        
        # Processing status: 'pending', 'downloaded', 'uploaded', 'linked', 'failed'
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('download_error', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    
    # Indexes for email_attachments
    op.create_index('idx_email_attach_log', 'email_attachments', ['email_log_id'])
    op.create_index('idx_email_attach_doc', 'email_attachments', ['document_id'])
    
    # -------------------------------------------------------------------------
    # 3. brevo_webhook_log - prevents duplicate webhook processing
    # -------------------------------------------------------------------------
    op.create_table(
        'brevo_webhook_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('webhook_id', sa.String(255), nullable=False, unique=True),
        sa.Column('event_type', sa.String(100), nullable=True),
        sa.Column('payload_hash', sa.String(64), nullable=True),  # SHA-256 hash for dedup
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('processed', sa.Boolean(), server_default='false'),
    )
    
    # Index for quick lookup
    op.create_index('idx_brevo_webhook_id', 'brevo_webhook_log', ['webhook_id'])
    
    # -------------------------------------------------------------------------
    # Enable Row Level Security
    # -------------------------------------------------------------------------
    op.execute('ALTER TABLE email_processing_log ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE email_attachments ENABLE ROW LEVEL SECURITY')
    # Note: brevo_webhook_log does NOT need RLS - it's for global deduplication
    
    # -------------------------------------------------------------------------
    # Create tenant isolation policies (same pattern as other tables)
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON email_processing_log
        USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON email_attachments
        USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
    """)
    
    # Force RLS for table owners
    op.execute('ALTER TABLE email_processing_log FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE email_attachments FORCE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Remove email intake tables."""
    
    # Drop policies first
    op.execute('DROP POLICY IF EXISTS tenant_isolation_policy ON email_attachments')
    op.execute('DROP POLICY IF EXISTS tenant_isolation_policy ON email_processing_log')
    
    # Drop indexes
    op.drop_index('idx_brevo_webhook_id', table_name='brevo_webhook_log')
    op.drop_index('idx_email_attach_doc', table_name='email_attachments')
    op.drop_index('idx_email_attach_log', table_name='email_attachments')
    op.drop_index('idx_email_log_sender', table_name='email_processing_log')
    op.drop_index('idx_email_log_status', table_name='email_processing_log')
    op.drop_index('idx_email_log_org_received', table_name='email_processing_log')
    
    # Drop tables (order matters due to FK)
    op.drop_table('brevo_webhook_log')
    op.drop_table('email_attachments')
    op.drop_table('email_processing_log')
