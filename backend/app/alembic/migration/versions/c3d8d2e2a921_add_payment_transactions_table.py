"""add payment transactions table

Revision ID: c3d8d2e2a921
Revises: b1e9b2f2c123
Create Date: 2026-03-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d8d2e2a921"
down_revision: Union[str, Sequence[str], None] = "b1e9b2f2c123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_name", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=False),
        sa.Column("provider_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("invoice_payload", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_payment_charge_id"),
    )
    op.create_index(
        op.f("ix_payment_transactions_telegram_id"),
        "payment_transactions",
        ["telegram_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_transactions_telegram_payment_charge_id"),
        "payment_transactions",
        ["telegram_payment_charge_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_transactions_telegram_payment_charge_id"), table_name="payment_transactions")
    op.drop_index(op.f("ix_payment_transactions_telegram_id"), table_name="payment_transactions")
    op.drop_table("payment_transactions")

