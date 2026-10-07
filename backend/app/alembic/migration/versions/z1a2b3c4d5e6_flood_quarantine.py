"""Global 12-24h flood quarantine on social accounts.

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "y0z1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column("flood_quarantined_until", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_social_accounts_flood_quarantined_until",
        "social_accounts",
        ["flood_quarantined_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_social_accounts_flood_quarantined_until", table_name="social_accounts")
    op.drop_column("social_accounts", "flood_quarantined_until")
