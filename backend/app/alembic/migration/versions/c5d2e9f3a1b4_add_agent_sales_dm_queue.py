"""Add agent_sales_dm_queue table for outbound message management

Revision ID: c5d2e9f3a1b4
Revises: b3e7d9a1c4f2
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d2e9f3a1b4"
down_revision: Union[str, Sequence[str], None] = "b3e7d9a1c4f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sales_dm_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("target_user_external_id", sa.String(length=128), nullable=False),
        sa.Column("source_chat_id", sa.String(length=128), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_sales_dm_queue_agent_id"), "agent_sales_dm_queue", ["agent_id"], unique=False)
    op.create_index(op.f("ix_agent_sales_dm_queue_status"), "agent_sales_dm_queue", ["status"], unique=False)
    op.create_index(op.f("ix_agent_sales_dm_queue_target_user_external_id"), "agent_sales_dm_queue", ["target_user_external_id"], unique=False)
    op.create_index(op.f("ix_agent_sales_dm_queue_created_at"), "agent_sales_dm_queue", ["created_at"], unique=False)
    op.create_index(op.f("ix_agent_sales_dm_queue_scheduled_for"), "agent_sales_dm_queue", ["scheduled_for"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_sales_dm_queue_scheduled_for"), table_name="agent_sales_dm_queue")
    op.drop_index(op.f("ix_agent_sales_dm_queue_created_at"), table_name="agent_sales_dm_queue")
    op.drop_index(op.f("ix_agent_sales_dm_queue_target_user_external_id"), table_name="agent_sales_dm_queue")
    op.drop_index(op.f("ix_agent_sales_dm_queue_status"), table_name="agent_sales_dm_queue")
    op.drop_index(op.f("ix_agent_sales_dm_queue_agent_id"), table_name="agent_sales_dm_queue")
    op.drop_table("agent_sales_dm_queue")
