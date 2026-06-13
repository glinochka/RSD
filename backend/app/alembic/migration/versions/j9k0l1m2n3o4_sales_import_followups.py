"""agent_sales_imported_contacts: reply tracking and follow-up timestamps

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-05-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j9k0l1m2n3o4"
down_revision: Union[str, Sequence[str], None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_sales_imported_contacts",
        sa.Column("reply_received_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "agent_sales_imported_contacts",
        sa.Column("follow_up_day_sent_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "agent_sales_imported_contacts",
        sa.Column("follow_up_week_sent_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "agent_sales_imported_contacts",
        sa.Column("follow_up_month_sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_agent_sales_imported_contacts_reply_received_at",
        "agent_sales_imported_contacts",
        ["reply_received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_sales_imported_contacts_reply_received_at",
        table_name="agent_sales_imported_contacts",
    )
    op.drop_column("agent_sales_imported_contacts", "follow_up_month_sent_at")
    op.drop_column("agent_sales_imported_contacts", "follow_up_week_sent_at")
    op.drop_column("agent_sales_imported_contacts", "follow_up_day_sent_at")
    op.drop_column("agent_sales_imported_contacts", "reply_received_at")
