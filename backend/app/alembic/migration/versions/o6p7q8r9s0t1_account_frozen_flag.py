"""frozen telegram accounts: session alive, actions blocked

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o6p7q8r9s0t1"
down_revision: Union[str, Sequence[str], None] = "n5o6p7q8r9s0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column("is_frozen", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("social_accounts", sa.Column("frozen_at", sa.DateTime(), nullable=True))
    op.create_index("ix_social_accounts_is_frozen", "social_accounts", ["is_frozen"])


def downgrade() -> None:
    op.drop_index("ix_social_accounts_is_frozen", table_name="social_accounts")
    op.drop_column("social_accounts", "frozen_at")
    op.drop_column("social_accounts", "is_frozen")
