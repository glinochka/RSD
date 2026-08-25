"""dmp bot pipeline: telegram bot + google sheets

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-25
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column("is_lead_qualification_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("custom_automations", sa.Column("telegram_bot_token_enc", sa.Text(), nullable=True))
    op.add_column("custom_automations", sa.Column("telegram_bot_username", sa.String(length=128), nullable=True))
    op.add_column("custom_automations", sa.Column("telegram_bot_webhook_secret", sa.String(length=64), nullable=True))
    op.add_column("custom_automations", sa.Column("google_sheets_spreadsheet_id", sa.String(length=256), nullable=True))
    op.add_column("custom_automations", sa.Column("google_sheets_worksheet", sa.String(length=128), nullable=True))
    op.add_column("custom_automations", sa.Column("google_sheets_credentials_enc", sa.Text(), nullable=True))

    op.create_table(
        "custom_bot_subscribers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="idle", nullable=False),
        sa.Column("pending_username", sa.String(length=64), nullable=True),
        sa.Column("pending_started_at", sa.DateTime(), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("authenticated_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custom_automation_id", "telegram_chat_id", name="uq_custom_bot_subscriber_chat"),
    )
    op.create_index("ix_custom_bot_subscribers_custom_automation_id", "custom_bot_subscribers", ["custom_automation_id"])
    op.create_index("ix_custom_bot_subscribers_telegram_chat_id", "custom_bot_subscribers", ["telegram_chat_id"])
    op.create_index("ix_custom_bot_subscribers_status", "custom_bot_subscribers", ["status"])

    conn = op.get_bind()
    now = _utcnow()
    exists = conn.execute(
        sa.text("SELECT id FROM custom_automations WHERE solution_slug = :slug"),
        {"slug": "dmp-bot"},
    ).scalar()
    if exists:
        return
    conn.execute(
        sa.text(
            """
            INSERT INTO custom_automations (
                name, client_name, industry, description, status,
                is_chat_monitoring_enabled, is_neurocommenting_enabled, is_digital_footprint_enabled,
                is_dmp_one_enabled, is_amocrm_enabled, is_shilling_enabled,
                is_lead_qualification_enabled, solution_kind, solution_slug,
                rotation_strategy, max_daily_messages_per_account, lead_warmup_enabled,
                created_at, updated_at
            ) VALUES (
                :name, :client_name, :industry, :description, :status,
                false, false, false,
                true, false, false,
                false, :solution_kind, :solution_slug,
                'round_robin', 50, false,
                :created_at, :updated_at
            )
            """
        ),
        {
            "name": "DMP-бот",
            "client_name": "DMP-бот",
            "industry": "dmp_bot",
            "description": "Связка DMP.one с Telegram-ботом и Google Таблицей. Без ИИ-агентов: лид приходит вебхуком, уходит в бот и в строку таблицы.",
            "status": "active",
            "solution_kind": "dmp_bot",
            "solution_slug": "dmp-bot",
            "created_at": now,
            "updated_at": now,
        },
    )
    automation_id = conn.execute(
        sa.text("SELECT id FROM custom_automations WHERE solution_slug = :slug"),
        {"slug": "dmp-bot"},
    ).scalar()
    if automation_id:
        conn.execute(
            sa.text(
                """
                INSERT INTO account_pools (
                    custom_automation_id, name, description, is_default, created_at, updated_at
                ) VALUES (
                    :custom_automation_id, 'Default', 'Default pool created automatically', true, :created_at, :updated_at
                )
                """
            ),
            {"custom_automation_id": automation_id, "created_at": now, "updated_at": now},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM custom_automations WHERE solution_slug = 'dmp-bot'"))
    op.drop_index("ix_custom_bot_subscribers_status", table_name="custom_bot_subscribers")
    op.drop_index("ix_custom_bot_subscribers_telegram_chat_id", table_name="custom_bot_subscribers")
    op.drop_index("ix_custom_bot_subscribers_custom_automation_id", table_name="custom_bot_subscribers")
    op.drop_table("custom_bot_subscribers")
    op.drop_column("custom_automations", "google_sheets_credentials_enc")
    op.drop_column("custom_automations", "google_sheets_worksheet")
    op.drop_column("custom_automations", "google_sheets_spreadsheet_id")
    op.drop_column("custom_automations", "telegram_bot_webhook_secret")
    op.drop_column("custom_automations", "telegram_bot_username")
    op.drop_column("custom_automations", "telegram_bot_token_enc")
    op.drop_column("custom_automations", "is_lead_qualification_enabled")
