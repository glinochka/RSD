"""account chat memberships for per-account join tracking

Revision ID: k1l2m3n4o5p6
Revises: j0d1e2f3a4b5
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, Sequence[str], None] = "j0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_chat_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("social_account_id", sa.Integer(), nullable=False),
        sa.Column("chat_target_id", sa.Integer(), nullable=False),
        sa.Column("join_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("join_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_join_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_join_error", sa.Text(), nullable=True),
        sa.Column("next_join_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chat_target_id"], ["chat_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("social_account_id", "chat_target_id", name="uq_account_chat_membership"),
    )
    op.create_index("ix_account_chat_memberships_automation", "account_chat_memberships", ["custom_automation_id"])
    op.create_index("ix_account_chat_memberships_chat", "account_chat_memberships", ["chat_target_id"])
    op.create_index("ix_account_chat_memberships_account", "account_chat_memberships", ["social_account_id"])
    op.create_index("ix_account_chat_memberships_join_status", "account_chat_memberships", ["join_status"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO account_chat_memberships (
                custom_automation_id, social_account_id, chat_target_id,
                join_status, join_attempts, joined_at, created_at, updated_at
            )
            SELECT
                ct.custom_automation_id,
                pa.social_account_id,
                ct.id,
                CASE
                    WHEN ct.join_status = 'joined' AND ct.joined_by_account_id = pa.social_account_id
                    THEN 'joined'
                    WHEN ct.join_status = 'joined'
                    THEN 'pending'
                    ELSE COALESCE(ct.join_status, 'pending')
                END,
                0,
                CASE
                    WHEN ct.join_status = 'joined' AND ct.joined_by_account_id = pa.social_account_id
                    THEN ct.joined_at
                    ELSE NULL
                END,
                NOW() AT TIME ZONE 'UTC',
                NOW() AT TIME ZONE 'UTC'
            FROM chat_targets ct
            JOIN account_pools ap ON ap.custom_automation_id = ct.custom_automation_id AND ap.is_default = true
            JOIN pool_accounts pa ON pa.account_pool_id = ap.id
            JOIN social_accounts sa ON sa.id = pa.social_account_id
            WHERE ct.is_active = true
              AND ct.provider = 'telegram'
              AND ct.source != 'test'
              AND sa.is_active = true
            ON CONFLICT (social_account_id, chat_target_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_account_chat_memberships_join_status", table_name="account_chat_memberships")
    op.drop_index("ix_account_chat_memberships_account", table_name="account_chat_memberships")
    op.drop_index("ix_account_chat_memberships_chat", table_name="account_chat_memberships")
    op.drop_index("ix_account_chat_memberships_automation", table_name="account_chat_memberships")
    op.drop_table("account_chat_memberships")
