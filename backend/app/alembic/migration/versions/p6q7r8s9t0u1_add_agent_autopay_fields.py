"""add agent autopay and payment flags

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-05-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, Sequence[str], None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("autopay_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "agents",
        sa.Column("yookassa_payment_method_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("autopay_duration_months", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("agents", sa.Column("autopay_last_attempt_at", sa.DateTime(), nullable=True))
    op.add_column("agents", sa.Column("autopay_last_error", sa.String(length=512), nullable=True))

    op.add_column(
        "website_payment_transactions",
        sa.Column("autopay_requested", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "website_payment_transactions",
        sa.Column("is_autopay_charge", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.alter_column("agents", "autopay_enabled", server_default=None)
    op.alter_column("agents", "autopay_duration_months", server_default=None)
    op.alter_column("website_payment_transactions", "autopay_requested", server_default=None)
    op.alter_column("website_payment_transactions", "is_autopay_charge", server_default=None)


def downgrade() -> None:
    op.drop_column("website_payment_transactions", "is_autopay_charge")
    op.drop_column("website_payment_transactions", "autopay_requested")
    op.drop_column("agents", "autopay_last_error")
    op.drop_column("agents", "autopay_last_attempt_at")
    op.drop_column("agents", "autopay_duration_months")
    op.drop_column("agents", "yookassa_payment_method_id")
    op.drop_column("agents", "autopay_enabled")
