"""ai_mop_leads: reply tracking and follow-up timestamps

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "y5z6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_mop_leads", sa.Column("reply_received_at", sa.DateTime(), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("follow_up_day_sent_at", sa.DateTime(), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("follow_up_week_sent_at", sa.DateTime(), nullable=True))
    op.add_column("ai_mop_leads", sa.Column("follow_up_month_sent_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_ai_mop_leads_reply_received_at",
        "ai_mop_leads",
        ["reply_received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_mop_leads_reply_received_at", table_name="ai_mop_leads")
    op.drop_column("ai_mop_leads", "follow_up_month_sent_at")
    op.drop_column("ai_mop_leads", "follow_up_week_sent_at")
    op.drop_column("ai_mop_leads", "follow_up_day_sent_at")
    op.drop_column("ai_mop_leads", "reply_received_at")
