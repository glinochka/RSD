"""Intercept hold and reauth timestamps.

Revision ID: g9a0b1c2d3e4
Revises: f8a9b0c1d2e3
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("intercept_reauthorized_at", sa.DateTime(), nullable=True))
    op.add_column("social_accounts", sa.Column("intercept_reauth_error", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("social_accounts", "intercept_reauth_error")
    op.drop_column("social_accounts", "intercept_reauthorized_at")
