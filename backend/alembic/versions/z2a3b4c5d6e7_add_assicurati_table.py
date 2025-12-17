"""add_assicurati_table

Revision ID: z2a3b4c5d6e7
Revises: y1t3u5v6w7x8
Create Date: 2024-12-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "z2a3b4c5d6e7"
down_revision: Union[str, None] = "y1t3u5v6w7x8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create assicurati table
    op.create_table(
        "assicurati",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_assicurati_org_name"),
    )

    # 2. Add assicurato_id FK to cases table
    op.add_column("cases", sa.Column("assicurato_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_cases_assicurato_id",
        "cases",
        "assicurati",
        ["assicurato_id"],
        ["id"],
    )
    # Add index for query performance (matches client_id pattern)
    op.create_index("idx_cases_assicurato", "cases", ["organization_id", "assicurato_id"])

    # 3. Enable RLS on assicurati table
    op.execute("ALTER TABLE assicurati ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE assicurati FORCE ROW LEVEL SECURITY")

    # 4. Create RLS policy for assicurati (same as clients)
    op.execute("""
        CREATE POLICY assicurati_org_isolation ON assicurati
        FOR ALL
        USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
    """)


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS assicurati_org_isolation ON assicurati")

    # Drop index
    op.drop_index("idx_cases_assicurato", "cases")

    # Drop FK from cases
    op.drop_constraint("fk_cases_assicurato_id", "cases", type_="foreignkey")
    op.drop_column("cases", "assicurato_id")

    # Drop table
    op.drop_table("assicurati")
