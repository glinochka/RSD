"""Sasha AI autodial integration for DMP.one.

Revision ID: k3l4m5n6o7p8
Revises: j2d3e4f5a6b7
Create Date: 2026-10-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, Sequence[str], None] = "j2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column("is_sasha_ai_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_upload_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_upload_format", sa.String(length=16), nullable=False, server_default="api"),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_webhook_secret", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_hmac_secret", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_auto_push", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_qualify_on_commit", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "custom_automations",
        sa.Column("sasha_notify_on_commit", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.add_column(
        "custom_leads",
        sa.Column("sasha_status", sa.String(length=32), nullable=True, index=True),
    )
    op.add_column("custom_leads", sa.Column("sasha_uploaded_at", sa.DateTime(), nullable=True))
    op.add_column("custom_leads", sa.Column("sasha_last_event_at", sa.DateTime(), nullable=True))
    op.add_column("custom_leads", sa.Column("sasha_lead_quality", sa.Integer(), nullable=True))
    op.add_column(
        "custom_leads",
        sa.Column("sasha_is_commit", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("custom_leads", sa.Column("sasha_summary", sa.Text(), nullable=True))
    op.add_column(
        "custom_leads",
        sa.Column("sasha_external_contact_id", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "sasha_ai_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "custom_automation_id",
            sa.Integer(),
            sa.ForeignKey("custom_automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "custom_lead_id",
            sa.Integer(),
            sa.ForeignKey("custom_leads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("call_list_id", sa.String(length=64), nullable=True),
        sa.Column("call_list_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("hangup_reason", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("is_commit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_facts", sa.Text(), nullable=True),
        sa.Column("agreements", sa.Text(), nullable=True),
        sa.Column("lead_quality", sa.Integer(), nullable=True),
        sa.Column("lead_destination", sa.String(length=32), nullable=True),
        sa.Column("agreements_status", sa.String(length=32), nullable=True),
        sa.Column("session_result_status", sa.String(length=32), nullable=True),
        sa.Column("session_result_reason", sa.String(length=64), nullable=True),
        sa.Column("record_url", sa.Text(), nullable=True),
        sa.Column("transcript", JSONB(), nullable=True),
        sa.Column("lead_transfer", JSONB(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("custom_automation_id", "event_id", name="uq_sasha_ai_call_event"),
    )
    op.create_index("ix_sasha_ai_calls_automation_id", "sasha_ai_calls", ["custom_automation_id"])
    op.create_index("ix_sasha_ai_calls_lead_id", "sasha_ai_calls", ["custom_lead_id"])
    op.create_index("ix_sasha_ai_calls_event_type", "sasha_ai_calls", ["event_type"])
    op.create_index("ix_sasha_ai_calls_created_at", "sasha_ai_calls", ["created_at"])
    op.create_index("ix_sasha_ai_calls_phone", "sasha_ai_calls", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_sasha_ai_calls_phone", table_name="sasha_ai_calls")
    op.drop_index("ix_sasha_ai_calls_created_at", table_name="sasha_ai_calls")
    op.drop_index("ix_sasha_ai_calls_event_type", table_name="sasha_ai_calls")
    op.drop_index("ix_sasha_ai_calls_lead_id", table_name="sasha_ai_calls")
    op.drop_index("ix_sasha_ai_calls_automation_id", table_name="sasha_ai_calls")
    op.drop_table("sasha_ai_calls")

    op.drop_column("custom_leads", "sasha_external_contact_id")
    op.drop_column("custom_leads", "sasha_summary")
    op.drop_column("custom_leads", "sasha_is_commit")
    op.drop_column("custom_leads", "sasha_lead_quality")
    op.drop_column("custom_leads", "sasha_last_event_at")
    op.drop_column("custom_leads", "sasha_uploaded_at")
    op.drop_column("custom_leads", "sasha_status")

    op.drop_column("custom_automations", "sasha_notify_on_commit")
    op.drop_column("custom_automations", "sasha_qualify_on_commit")
    op.drop_column("custom_automations", "sasha_auto_push")
    op.drop_column("custom_automations", "sasha_hmac_secret")
    op.drop_column("custom_automations", "sasha_webhook_secret")
    op.drop_column("custom_automations", "sasha_upload_format")
    op.drop_column("custom_automations", "sasha_upload_url")
    op.drop_column("custom_automations", "is_sasha_ai_enabled")
