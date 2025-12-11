"""Add client enrichment fields for ICE feature

Revision ID: s5n7o8p9q0r1
Revises: r4m5n6o7p8q9
Create Date: 2025-12-11

ICE (Intelligent Client Enrichment) feature columns:
- logo_url: Favicon from Google Favicon API
- address_street, city, zip_code, province, country: Sede Legale
- website: Official company website
- referente, email, telefono: Contact info (manual entry)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's5n7o8p9q0r1'
down_revision = 'r4m5n6o7p8q9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ICE Enrichment Fields
    op.add_column('clients', sa.Column('logo_url', sa.String(1024), nullable=True))
    op.add_column('clients', sa.Column('address_street', sa.String(500), nullable=True))
    op.add_column('clients', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('zip_code', sa.String(20), nullable=True))
    op.add_column('clients', sa.Column('province', sa.String(10), nullable=True))
    op.add_column('clients', sa.Column('country', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('website', sa.String(500), nullable=True))
    
    # Contact fields
    op.add_column('clients', sa.Column('referente', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('telefono', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'telefono')
    op.drop_column('clients', 'email')
    op.drop_column('clients', 'referente')
    op.drop_column('clients', 'website')
    op.drop_column('clients', 'country')
    op.drop_column('clients', 'province')
    op.drop_column('clients', 'zip_code')
    op.drop_column('clients', 'city')
    op.drop_column('clients', 'address_street')
    op.drop_column('clients', 'logo_url')
