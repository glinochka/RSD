"""lazy join coverage: watcher shards, actor priority, pending actions

Revision ID: m4n5o6p7q8r9
Revises: l2m3n4o5p6q7
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, Sequence[str], None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_chat_memberships",
        sa.Column("purpose", sa.String(length=32), server_default="watcher", nullable=False),
    )
    op.add_column(
        "account_chat_memberships",
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_account_chat_memberships_purpose",
        "account_chat_memberships",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        "ix_account_chat_memberships_priority",
        "account_chat_memberships",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_account_chat_memberships_join_queue",
        "account_chat_memberships",
        ["custom_automation_id", "priority", "join_status"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY chat_target_id
                           ORDER BY CASE WHEN join_status = 'joined' THEN 0 ELSE 1 END, id
                       ) AS rn
                FROM account_chat_memberships
            )
            UPDATE account_chat_memberships AS m
            SET purpose = CASE WHEN r.rn = 1 THEN 'watcher' ELSE 'actor' END,
                priority = 0
            FROM ranked AS r
            WHERE m.id = r.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM account_chat_memberships
            WHERE purpose = 'actor'
              AND priority = 0
              AND join_status NOT IN ('joined', 'joining')
            """
        )
    )

    op.create_table(
        "pending_chat_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("chat_target_id", sa.Integer(), nullable=False),
        sa.Column("social_account_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chat_target_id"], ["chat_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custom_automation_id", "action_type", "target_id", name="uq_pending_chat_action"),
    )
    op.create_index(
        "ix_pending_chat_actions_automation",
        "pending_chat_actions",
        ["custom_automation_id"],
        unique=False,
    )
    op.create_index(
        "ix_pending_chat_actions_chat",
        "pending_chat_actions",
        ["chat_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_pending_chat_actions_status",
        "pending_chat_actions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pending_chat_actions_status", table_name="pending_chat_actions")
    op.drop_index("ix_pending_chat_actions_chat", table_name="pending_chat_actions")
    op.drop_index("ix_pending_chat_actions_automation", table_name="pending_chat_actions")
    op.drop_table("pending_chat_actions")
    op.drop_index("ix_account_chat_memberships_join_queue", table_name="account_chat_memberships")
    op.drop_index("ix_account_chat_memberships_priority", table_name="account_chat_memberships")
    op.drop_index("ix_account_chat_memberships_purpose", table_name="account_chat_memberships")
    op.drop_column("account_chat_memberships", "priority")
    op.drop_column("account_chat_memberships", "purpose")
