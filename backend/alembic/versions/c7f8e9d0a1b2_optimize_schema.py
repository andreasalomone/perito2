"""optimize_schema

Revision ID: c7f8e9d0a1b2
Revises: 81c0949c01b9
Create Date: 2025-12-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7f8e9d0a1b2'
down_revision = '81c0949c01b9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Indexes for Performance
    # Dashboard: Filter by Org, Sort by Date
    op.create_index('idx_cases_dashboard', 'cases', ['organization_id', sa.text('created_at DESC')])
    
    # Foreign Key Indexes (Missing in original schema)
    op.create_index('idx_documents_case', 'documents', ['case_id'])
    op.create_index('idx_report_versions_case', 'report_versions', ['case_id'])
    op.create_index('idx_ml_pairs_case', 'ml_training_pairs', ['case_id'])
    op.create_index('idx_users_org', 'users', ['organization_id'])
    
    # 2. Constraints for Integrity
    # Unique Clients per Organization
    op.create_unique_constraint('uq_clients_org_name', 'clients', ['organization_id', 'name'])
    
    # 3. Cascading Deletes (Cleanup)
    # Documents -> Case
    op.drop_constraint('documents_case_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key('documents_case_id_fkey', 'documents', 'cases', ['case_id'], ['id'], ondelete='CASCADE')
    
    # Report Versions -> Case
    op.drop_constraint('report_versions_case_id_fkey', 'report_versions', type_='foreignkey')
    op.create_foreign_key('report_versions_case_id_fkey', 'report_versions', 'cases', ['case_id'], ['id'], ondelete='CASCADE')


def downgrade():
    # Revert Cascades
    op.drop_constraint('report_versions_case_id_fkey', 'report_versions', type_='foreignkey')
    op.create_foreign_key('report_versions_case_id_fkey', 'report_versions', 'cases', ['case_id'], ['id'])
    
    op.drop_constraint('documents_case_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key('documents_case_id_fkey', 'documents', 'cases', ['case_id'], ['id'])
    
    # Remove Constraints
    op.drop_constraint('uq_clients_org_name', 'clients', type_='unique')
    
    # Remove Indexes
    op.drop_index('idx_users_org', table_name='users')
    op.drop_index('idx_ml_pairs_case', table_name='ml_training_pairs')
    op.drop_index('idx_report_versions_case', table_name='report_versions')
    op.drop_index('idx_documents_case', table_name='documents')
    op.drop_index('idx_cases_dashboard', table_name='cases')
