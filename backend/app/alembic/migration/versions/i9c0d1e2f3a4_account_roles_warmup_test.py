"""account roles, warmup and test lab targets

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "i9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "h8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column(
            "account_warmup_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "custom_automations",
        sa.Column(
            "account_warmup_usernames",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "custom_automations",
        sa.Column(
            "account_warmup_messages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "custom_automations",
        sa.Column("test_channel_username", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("test_chat_username", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "pool_accounts",
        sa.Column(
            "roles",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "pool_accounts",
        sa.Column(
            "warmup_status",
            sa.String(length=32),
            server_default="idle",
            nullable=False,
        ),
    )
    op.add_column("pool_accounts", sa.Column("warmup_started_at", sa.DateTime(), nullable=True))
    op.add_column("pool_accounts", sa.Column("warmup_last_dialog_at", sa.DateTime(), nullable=True))
    op.add_column(
        "pool_accounts",
        sa.Column("warmup_dialog_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_pool_accounts_warmup_status", "pool_accounts", ["warmup_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pool_accounts_warmup_status", table_name="pool_accounts")
    op.drop_column("pool_accounts", "warmup_dialog_count")
    op.drop_column("pool_accounts", "warmup_last_dialog_at")
    op.drop_column("pool_accounts", "warmup_started_at")
    op.drop_column("pool_accounts", "warmup_status")
    op.drop_column("pool_accounts", "roles")
    op.drop_column("custom_automations", "test_chat_username")
    op.drop_column("custom_automations", "test_channel_username")
    op.drop_column("custom_automations", "account_warmup_messages")
    op.drop_column("custom_automations", "account_warmup_usernames")
    op.drop_column("custom_automations", "account_warmup_enabled")
