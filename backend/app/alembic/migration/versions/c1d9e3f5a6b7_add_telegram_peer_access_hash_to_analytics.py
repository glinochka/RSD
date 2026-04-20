"""add telegram_peer_access_hash to agent_analytics_messages

Revision ID: c1d9e3f5a6b7
Revises: a1f6c9d2e4b7
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d9e3f5a6b7"
down_revision: Union[str, Sequence[str], None] = "a1f6c9d2e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_analytics_messages",
        sa.Column("telegram_peer_access_hash", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_analytics_messages", "telegram_peer_access_hash")
