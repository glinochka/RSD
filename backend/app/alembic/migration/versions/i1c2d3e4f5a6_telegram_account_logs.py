"""Per-account Telegram RPC logs in human language.

Revision ID: i1c2d3e4f5a6
Revises: h0b1c2d3e4f5
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "h0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_account_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("social_account_id", sa.Integer(), sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("rpc_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("result", sa.String(length=16), nullable=False, server_default="ok"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_telegram_account_logs_automation_id", "telegram_account_logs", ["custom_automation_id"])
    op.create_index("ix_telegram_account_logs_account_id", "telegram_account_logs", ["social_account_id"])
    op.create_index("ix_telegram_account_logs_created_at", "telegram_account_logs", ["created_at"])
    op.create_index("ix_telegram_account_logs_result", "telegram_account_logs", ["result"])


def downgrade() -> None:
    op.drop_index("ix_telegram_account_logs_result", table_name="telegram_account_logs")
    op.drop_index("ix_telegram_account_logs_created_at", table_name="telegram_account_logs")
    op.drop_index("ix_telegram_account_logs_account_id", table_name="telegram_account_logs")
    op.drop_index("ix_telegram_account_logs_automation_id", table_name="telegram_account_logs")
    op.drop_table("telegram_account_logs")
