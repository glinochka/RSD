"""ai_mop_leads: outreach fields and failure_stage

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x4y5z6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "w3x4y5z6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_mop_leads", sa.Column("telegram", sa.String(length=512), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("whatsapp", sa.String(length=512), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("outreach_channel", sa.String(length=32), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("outreach_target", sa.String(length=256), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("failure_stage", sa.String(length=32), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("dm_queue_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_ai_mop_leads_failure_stage"), "ai_mop_leads", ["failure_stage"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_mop_leads_failure_stage"), table_name="ai_mop_leads")
    op.drop_column("ai_mop_leads", "dm_queue_id")
    op.drop_column("ai_mop_leads", "failure_stage")
    op.drop_column("ai_mop_leads", "outreach_target")
    op.drop_column("ai_mop_leads", "outreach_channel")
    op.drop_column("ai_mop_leads", "whatsapp")
    op.drop_column("ai_mop_leads", "telegram")
