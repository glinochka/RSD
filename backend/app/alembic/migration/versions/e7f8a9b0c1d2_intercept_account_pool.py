"""Separate intercept pool for stolen sessions.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_pools",
        sa.Column("purpose", sa.String(length=32), nullable=False, server_default="farm"),
    )
    op.create_index("ix_account_pools_purpose", "account_pools", ["purpose"], unique=False)
    op.add_column(
        "social_accounts",
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="farm"),
    )
    op.create_index("ix_social_accounts_origin", "social_accounts", ["origin"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_social_accounts_origin", table_name="social_accounts")
    op.drop_column("social_accounts", "origin")
    op.drop_index("ix_account_pools_purpose", table_name="account_pools")
    op.drop_column("account_pools", "purpose")
