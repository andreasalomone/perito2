"""add_casestatus_values

Revision ID: 20fc7bb876cc
Revises: 19fc7bb876cb
Create Date: 2025-12-04 17:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20fc7bb876cc'
down_revision = '19fc7bb876cb'
branch_labels = None
depends_on = None

def upgrade():
    # Postgres specific command to add value to enum
    # We must use execute because alembic doesn't abstract this well for existing types
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block
    with op.get_context().autocommit_block():
        # CaseStatus updates
        op.execute("ALTER TYPE casestatus ADD VALUE IF NOT EXISTS 'GENERATING'")
        op.execute("ALTER TYPE casestatus ADD VALUE IF NOT EXISTS 'PROCESSING'")
        op.execute("ALTER TYPE casestatus ADD VALUE IF NOT EXISTS 'ERROR'")
        
        # ExtractionStatus updates
        op.execute("ALTER TYPE extractionstatus ADD VALUE IF NOT EXISTS 'PENDING'")

def downgrade():
    # Cannot remove enum values in Postgres easily
    pass
