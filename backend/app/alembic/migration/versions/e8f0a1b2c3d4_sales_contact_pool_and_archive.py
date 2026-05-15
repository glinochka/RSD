"""sales_outbound_contacts: common pool, archive, daily allocation

Revision ID: e8f0a1b2c3d4
Revises: d1e2f3a4b5c7
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_team_members",
        sa.Column("last_daily_allocation_date", sa.Date(), nullable=True),
    )
    op.add_column("sales_outbound_contacts", sa.Column("assigned_at", sa.DateTime(), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.alter_column("sales_outbound_contacts", "assignee_id", existing_type=sa.Integer(), nullable=True)
    op.create_index("ix_sales_outbound_contacts_archived_at", "sales_outbound_contacts", ["archived_at"], unique=False)
    op.create_index("ix_sales_outbound_contacts_assigned_at", "sales_outbound_contacts", ["assigned_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sales_outbound_contacts_assigned_at", table_name="sales_outbound_contacts")
    op.drop_index("ix_sales_outbound_contacts_archived_at", table_name="sales_outbound_contacts")
    op.drop_column("sales_outbound_contacts", "archived_at")
    op.drop_column("sales_outbound_contacts", "assigned_at")
    op.drop_column("sales_team_members", "last_daily_allocation_date")
    op.alter_column("sales_outbound_contacts", "assignee_id", existing_type=sa.Integer(), nullable=False)
