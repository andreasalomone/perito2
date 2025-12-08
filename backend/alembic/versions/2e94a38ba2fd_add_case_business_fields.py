"""Add case business fields

Revision ID: 2e94a38ba2fd
Revises: o1j2k3l4m5n6
Create Date: 2025-12-08 09:11:05.760721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2e94a38ba2fd'
down_revision: Union[str, Sequence[str], None] = 'o1j2k3l4m5n6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 24 new business fields to cases table."""
    # Reference number
    op.add_column('cases', sa.Column('ns_rif', sa.Integer(), nullable=True))
    
    # Policy & Type
    op.add_column('cases', sa.Column('polizza', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('tipo_perizia', sa.String(length=255), nullable=True))
    
    # Goods
    op.add_column('cases', sa.Column('merce', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('descrizione_merce', sa.String(length=255), nullable=True))
    
    # Financial
    op.add_column('cases', sa.Column('riserva', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('cases', sa.Column('importo_liquidato', sa.Numeric(precision=15, scale=2), nullable=True))
    
    # People & Roles
    op.add_column('cases', sa.Column('perito', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('cliente', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('rif_cliente', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('gestore', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('assicurato', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('riferimento_assicurato', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('mittenti', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('broker', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('riferimento_broker', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('destinatari', sa.String(length=255), nullable=True))
    
    # Transport
    op.add_column('cases', sa.Column('mezzo_di_trasporto', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('descrizione_mezzo_di_trasporto', sa.String(length=255), nullable=True))
    
    # Location & Processing
    op.add_column('cases', sa.Column('luogo_intervento', sa.String(length=255), nullable=True))
    op.add_column('cases', sa.Column('genere_lavorazione', sa.String(length=255), nullable=True))
    
    # Dates
    op.add_column('cases', sa.Column('data_sinistro', sa.Date(), nullable=True))
    op.add_column('cases', sa.Column('data_incarico', sa.Date(), nullable=True))
    
    # Notes
    op.add_column('cases', sa.Column('note', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove all 24 business fields from cases table."""
    op.drop_column('cases', 'note')
    op.drop_column('cases', 'data_incarico')
    op.drop_column('cases', 'data_sinistro')
    op.drop_column('cases', 'genere_lavorazione')
    op.drop_column('cases', 'luogo_intervento')
    op.drop_column('cases', 'descrizione_mezzo_di_trasporto')
    op.drop_column('cases', 'mezzo_di_trasporto')
    op.drop_column('cases', 'destinatari')
    op.drop_column('cases', 'riferimento_broker')
    op.drop_column('cases', 'broker')
    op.drop_column('cases', 'mittenti')
    op.drop_column('cases', 'riferimento_assicurato')
    op.drop_column('cases', 'assicurato')
    op.drop_column('cases', 'gestore')
    op.drop_column('cases', 'rif_cliente')
    op.drop_column('cases', 'cliente')
    op.drop_column('cases', 'perito')
    op.drop_column('cases', 'importo_liquidato')
    op.drop_column('cases', 'riserva')
    op.drop_column('cases', 'descrizione_merce')
    op.drop_column('cases', 'merce')
    op.drop_column('cases', 'tipo_perizia')
    op.drop_column('cases', 'polizza')
    op.drop_column('cases', 'ns_rif')
