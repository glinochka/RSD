"""add website payment transactions

Revision ID: e1a4f83d9f12
Revises: d5a1c3f4e567
Create Date: 2026-03-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1a4f83d9f12"
down_revision: Union[str, Sequence[str], None] = "d5a1c3f4e567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "website_payment_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_name", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("yookassa_payment_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("yookassa_payment_id"),
    )
    op.create_index(
        op.f("ix_website_payment_transactions_user_id"),
        "website_payment_transactions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_website_payment_transactions_yookassa_payment_id"),
        "website_payment_transactions",
        ["yookassa_payment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_website_payment_transactions_yookassa_payment_id"), table_name="website_payment_transactions")
    op.drop_index(op.f("ix_website_payment_transactions_user_id"), table_name="website_payment_transactions")
    op.drop_table("website_payment_transactions")

