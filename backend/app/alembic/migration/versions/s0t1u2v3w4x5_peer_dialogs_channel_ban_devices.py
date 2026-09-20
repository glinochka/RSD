"""peer dialogs, channel-write ban, warmup pacing, device fingerprints

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "s0t1u2v3w4x5"
down_revision: Union[str, Sequence[str], None] = "r9s0t1u2v3w4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("telegram_device", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("social_accounts", sa.Column("spare_telegram_device", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "social_accounts",
        sa.Column("is_channel_banned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("ix_social_accounts_is_channel_banned", "social_accounts", ["is_channel_banned"])
    op.add_column(
        "pool_accounts",
        sa.Column("warmup_message_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("pool_accounts", sa.Column("warmup_next_at", sa.DateTime(), nullable=True))
    op.create_index("ix_pool_accounts_warmup_next_at", "pool_accounts", ["warmup_next_at"])
    op.create_table(
        "custom_account_peer_dialogs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_low_id", sa.Integer(), sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_high_id", sa.Integer(), sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="idle", nullable=False),
        sa.Column("day_key", sa.String(length=16), nullable=True),
        sa.Column("daily_target", sa.Integer(), server_default="6", nullable=False),
        sa.Column("messages_today", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_sender_id", sa.Integer(), sa.ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("next_send_at", sa.DateTime(), nullable=True),
        sa.Column("last_text", sa.Text(), nullable=True),
        sa.Column("history", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("custom_automation_id", "account_low_id", "account_high_id", name="uq_peer_dialog_pair"),
    )
    op.create_index("ix_custom_account_peer_dialogs_custom_automation_id", "custom_account_peer_dialogs", ["custom_automation_id"])
    op.create_index("ix_custom_account_peer_dialogs_status", "custom_account_peer_dialogs", ["status"])
    op.create_index("ix_custom_account_peer_dialogs_next_send_at", "custom_account_peer_dialogs", ["next_send_at"])
    op.create_index("ix_custom_account_peer_dialogs_day_key", "custom_account_peer_dialogs", ["day_key"])


def downgrade() -> None:
    op.drop_index("ix_custom_account_peer_dialogs_day_key", table_name="custom_account_peer_dialogs")
    op.drop_index("ix_custom_account_peer_dialogs_next_send_at", table_name="custom_account_peer_dialogs")
    op.drop_index("ix_custom_account_peer_dialogs_status", table_name="custom_account_peer_dialogs")
    op.drop_index("ix_custom_account_peer_dialogs_custom_automation_id", table_name="custom_account_peer_dialogs")
    op.drop_table("custom_account_peer_dialogs")
    op.drop_index("ix_pool_accounts_warmup_next_at", table_name="pool_accounts")
    op.drop_column("pool_accounts", "warmup_next_at")
    op.drop_column("pool_accounts", "warmup_message_index")
    op.drop_index("ix_social_accounts_is_channel_banned", table_name="social_accounts")
    op.drop_column("social_accounts", "is_channel_banned")
    op.drop_column("social_accounts", "spare_telegram_device")
    op.drop_column("social_accounts", "telegram_device")
