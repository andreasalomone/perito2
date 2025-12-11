"""Merge ICE feature migration with main branch

Revision ID: t6o8p9q0r1s2
Revises: 9d8030865527, s5n7o8p9q0r1
Create Date: 2025-12-11

Merges the ICE (Intelligent Client Enrichment) feature migration
with the existing main branch migration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 't6o8p9q0r1s2'
down_revision = ('9d8030865527', 's5n7o8p9q0r1')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
