"""add telephony calls and turns tables

Revision ID: e2f3a4b5c6d7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_telephony_calls",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("external_call_id", sa.String(length=191), nullable=False),
        sa.Column("caller_e164", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ringing"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["agent_channel_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "external_call_id", name="uq_agent_telephony_calls_connection_external"),
    )
    op.create_index(
        op.f("ix_agent_telephony_calls_connection_id"),
        "agent_telephony_calls",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_telephony_calls_agent_id"),
        "agent_telephony_calls",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_telephony_calls_status"),
        "agent_telephony_calls",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_telephony_calls_started_at"),
        "agent_telephony_calls",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "agent_telephony_turns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["agent_telephony_calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_telephony_turns_call_id"),
        "agent_telephony_turns",
        ["call_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_telephony_turns_created_at"),
        "agent_telephony_turns",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_telephony_turns_created_at"), table_name="agent_telephony_turns")
    op.drop_index(op.f("ix_agent_telephony_turns_call_id"), table_name="agent_telephony_turns")
    op.drop_table("agent_telephony_turns")
    op.drop_index(op.f("ix_agent_telephony_calls_started_at"), table_name="agent_telephony_calls")
    op.drop_index(op.f("ix_agent_telephony_calls_status"), table_name="agent_telephony_calls")
    op.drop_index(op.f("ix_agent_telephony_calls_agent_id"), table_name="agent_telephony_calls")
    op.drop_index(op.f("ix_agent_telephony_calls_connection_id"), table_name="agent_telephony_calls")
    op.drop_table("agent_telephony_calls")
