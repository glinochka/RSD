"""sales CRM: dedup_key, allocation events, assignee FK SET NULL

Revision ID: c1d2e3f4a5b6
Revises: b4c8e2a1d5f0
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b4c8e2a1d5f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_team_members",
        sa.Column(
            "daily_allocation_events",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "sales_outbound_contacts",
        sa.Column("dedup_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_sales_outbound_contacts_dedup_key",
        "sales_outbound_contacts",
        ["dedup_key"],
        unique=False,
    )

    # PostgreSQL: CASCADE -> SET NULL (контакты не удаляются вместе с сотрудником).
    op.drop_constraint(
        "sales_outbound_contacts_assignee_id_fkey",
        "sales_outbound_contacts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "sales_outbound_contacts_assignee_id_fkey",
        "sales_outbound_contacts",
        "sales_team_members",
        ["assignee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "sales_outbound_contacts_assignee_id_fkey",
        "sales_outbound_contacts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "sales_outbound_contacts_assignee_id_fkey",
        "sales_outbound_contacts",
        "sales_team_members",
        ["assignee_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_sales_outbound_contacts_dedup_key", table_name="sales_outbound_contacts")
    op.drop_column("sales_outbound_contacts", "dedup_key")
    op.drop_column("sales_team_members", "daily_allocation_events")
