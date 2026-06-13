"""add agent billing fields and payment kind on website transactions

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("activation_paid_at", sa.DateTime(), nullable=True))
    op.add_column("agents", sa.Column("maintenance_paid_until", sa.Date(), nullable=True))
    op.add_column(
        "website_payment_transactions",
        sa.Column("agent_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "website_payment_transactions",
        sa.Column(
            "payment_kind",
            sa.String(length=32),
            nullable=False,
            server_default="subscription",
        ),
    )
    op.create_foreign_key(
        "fk_website_payment_transactions_agent_id",
        "website_payment_transactions",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_website_payment_transactions_agent_id",
        "website_payment_transactions",
        ["agent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_website_payment_transactions_agent_id", table_name="website_payment_transactions")
    op.drop_constraint(
        "fk_website_payment_transactions_agent_id",
        "website_payment_transactions",
        type_="foreignkey",
    )
    op.drop_column("website_payment_transactions", "payment_kind")
    op.drop_column("website_payment_transactions", "agent_id")
    op.drop_column("agents", "maintenance_paid_until")
    op.drop_column("agents", "activation_paid_at")
