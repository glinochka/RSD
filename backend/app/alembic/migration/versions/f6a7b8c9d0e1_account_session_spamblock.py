"""account session and spamblock flags

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column("is_spamblocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("social_accounts", sa.Column("spamblocked_at", sa.DateTime(), nullable=True))
    op.add_column("social_accounts", sa.Column("spamblock_checked_at", sa.DateTime(), nullable=True))
    op.create_index("ix_social_accounts_is_spamblocked", "social_accounts", ["is_spamblocked"])


def downgrade() -> None:
    op.drop_index("ix_social_accounts_is_spamblocked", table_name="social_accounts")
    op.drop_column("social_accounts", "spamblock_checked_at")
    op.drop_column("social_accounts", "spamblocked_at")
    op.drop_column("social_accounts", "is_spamblocked")
