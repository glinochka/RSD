"""ai_mop_leads and ai_mop_agent_assignments for platform sales runtime

Revision ID: w3x4y5z6a7b8
Revises: u2v3w4x5y6z7
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w3x4y5z6a7b8"
down_revision: Union[str, Sequence[str], None] = "u2v3w4x5y6z7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_mop_leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_name", sa.String(length=512), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("lpr_name", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=256), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("category", sa.String(length=256), nullable=True),
        sa.Column("yandex_url", sa.String(length=512), nullable=True),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("assigned_agent_id", sa.Integer(), nullable=True),
        sa.Column("provisioned_user_id", sa.Integer(), nullable=True),
        sa.Column("provisioned_agent_id", sa.Integer(), nullable=True),
        sa.Column("provisioned_website_id", sa.Integer(), nullable=True),
        sa.Column("website_url", sa.String(length=512), nullable=True),
        sa.Column("temp_password", sa.String(length=32), nullable=True),
        sa.Column("outreach_sent_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("import_batch_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provisioned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provisioned_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provisioned_website_id"], ["websites.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_ai_mop_lead_dedup"),
    )
    op.create_index(op.f("ix_ai_mop_leads_email"), "ai_mop_leads", ["email"], unique=False)
    op.create_index(op.f("ix_ai_mop_leads_status"), "ai_mop_leads", ["status"], unique=False)
    op.create_index(op.f("ix_ai_mop_leads_assigned_agent_id"), "ai_mop_leads", ["assigned_agent_id"], unique=False)
    op.create_index(op.f("ix_ai_mop_leads_outreach_sent_at"), "ai_mop_leads", ["outreach_sent_at"], unique=False)
    op.create_index(op.f("ix_ai_mop_leads_import_batch_id"), "ai_mop_leads", ["import_batch_id"], unique=False)
    op.create_index(op.f("ix_ai_mop_leads_created_at"), "ai_mop_leads", ["created_at"], unique=False)

    op.create_table(
        "ai_mop_agent_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_busy", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.Column("leads_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("leads_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("leads_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_ai_mop_agent_assignment"),
    )
    op.create_index(op.f("ix_ai_mop_agent_assignments_agent_id"), "ai_mop_agent_assignments", ["agent_id"], unique=False)
    op.create_index(op.f("ix_ai_mop_agent_assignments_cooldown_until"), "ai_mop_agent_assignments", ["cooldown_until"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_mop_agent_assignments_cooldown_until"), table_name="ai_mop_agent_assignments")
    op.drop_index(op.f("ix_ai_mop_agent_assignments_agent_id"), table_name="ai_mop_agent_assignments")
    op.drop_table("ai_mop_agent_assignments")
    op.drop_index(op.f("ix_ai_mop_leads_created_at"), table_name="ai_mop_leads")
    op.drop_index(op.f("ix_ai_mop_leads_import_batch_id"), table_name="ai_mop_leads")
    op.drop_index(op.f("ix_ai_mop_leads_outreach_sent_at"), table_name="ai_mop_leads")
    op.drop_index(op.f("ix_ai_mop_leads_assigned_agent_id"), table_name="ai_mop_leads")
    op.drop_index(op.f("ix_ai_mop_leads_status"), table_name="ai_mop_leads")
    op.drop_index(op.f("ix_ai_mop_leads_email"), table_name="ai_mop_leads")
    op.drop_table("ai_mop_leads")
