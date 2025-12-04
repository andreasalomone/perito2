"""update_documents_jsonb

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2025-12-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = '9db07502eeea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert JSON to JSONB
    op.alter_column('documents', 'ai_extracted_data',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               postgresql_using='ai_extracted_data::jsonb')


def downgrade() -> None:
    # Revert JSONB to JSON
    op.alter_column('documents', 'ai_extracted_data',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=postgresql.JSON(astext_type=sa.Text()),
               postgresql_using='ai_extracted_data::json')
