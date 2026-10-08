"""Cache Telegram authorization count on pool accounts.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("telegram_session_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("social_accounts", "telegram_session_count")
