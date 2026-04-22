"""add crm tool fields to agent analytics messages

Revision ID: e2b4a9c7d1f3
Revises: c4f7e2a1b9d3
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2b4a9c7d1f3"
down_revision: Union[str, Sequence[str], None] = ("c4f7e2a1b9d3", "c1d9e3f5a6b7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_analytics_messages", sa.Column("tool_name", sa.String(length=64), nullable=True))
    op.add_column("agent_analytics_messages", sa.Column("tool_args_hash", sa.String(length=64), nullable=True))
    op.add_column("agent_analytics_messages", sa.Column("tool_status", sa.String(length=24), nullable=True))
    op.add_column("agent_analytics_messages", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("agent_analytics_messages", sa.Column("crm_provider", sa.String(length=32), nullable=True))

    op.create_index(op.f("ix_agent_analytics_messages_tool_name"), "agent_analytics_messages", ["tool_name"], unique=False)
    op.create_index(
        op.f("ix_agent_analytics_messages_tool_args_hash"),
        "agent_analytics_messages",
        ["tool_args_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_tool_status"),
        "agent_analytics_messages",
        ["tool_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_analytics_messages_crm_provider"),
        "agent_analytics_messages",
        ["crm_provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_analytics_messages_crm_provider"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_tool_status"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_tool_args_hash"), table_name="agent_analytics_messages")
    op.drop_index(op.f("ix_agent_analytics_messages_tool_name"), table_name="agent_analytics_messages")

    op.drop_column("agent_analytics_messages", "crm_provider")
    op.drop_column("agent_analytics_messages", "latency_ms")
    op.drop_column("agent_analytics_messages", "tool_status")
    op.drop_column("agent_analytics_messages", "tool_args_hash")
    op.drop_column("agent_analytics_messages", "tool_name")
