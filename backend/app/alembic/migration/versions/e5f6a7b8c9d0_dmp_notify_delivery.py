"""persist dmp notify delivery state

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_leads", sa.Column("bot_notified_at", sa.DateTime(), nullable=True))
    op.add_column("custom_leads", sa.Column("sheets_synced_at", sa.DateTime(), nullable=True))
    op.add_column(
        "custom_leads",
        sa.Column("bot_notified_chat_ids", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("custom_leads", "bot_notified_chat_ids")
    op.drop_column("custom_leads", "sheets_synced_at")
    op.drop_column("custom_leads", "bot_notified_at")
