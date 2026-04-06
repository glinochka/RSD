"""add agent analytics messages table

Revision ID: a7d1e2c9f4b0
Revises: f9c1d4b8a3e0
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7d1e2c9f4b0"
down_revision: Union[str, Sequence[str], None] = "f9c1d4b8a3e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_analytics_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="telegram"),
        sa.Column("user_external_id", sa.String(length=128), nullable=True),
        sa.Column("user_display_name", sa.String(length=128), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_agent_id"),
        "agent_analytics_messages",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_bot_id"),
        "agent_analytics_messages",
        ["bot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_role"),
        "agent_analytics_messages",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_user_external_id"),
        "agent_analytics_messages",
        ["user_external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_created_at"),
        "agent_analytics_messages",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_analytics_messages_bot_user_created",
        "agent_analytics_messages",
        ["bot_id", "user_external_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_analytics_messages_bot_user_created", table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_created_at"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_user_external_id"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_role"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_bot_id"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_agent_id"), table_name="agent_analytics_messages")
    op.drop_table("agent_analytics_messages")
