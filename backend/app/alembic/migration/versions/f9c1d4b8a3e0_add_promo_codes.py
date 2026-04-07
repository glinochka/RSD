"""add promo codes and discount fields

Revision ID: f9c1d4b8a3e0
Revises: e8b1c2d4f901
Create Date: 2026-04-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9c1d4b8a3e0"
down_revision: Union[str, Sequence[str], None] = "e8b1c2d4f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_promo_codes_code"), "promo_codes", ["code"], unique=True)
    op.create_index(op.f("ix_promo_codes_created_at"), "promo_codes", ["created_at"], unique=False)

    op.add_column(
        "website_payment_transactions",
        sa.Column("original_total_amount", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "website_payment_transactions",
        sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "website_payment_transactions",
        sa.Column("promo_code", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE website_payment_transactions "
        "SET original_total_amount = total_amount "
        "WHERE original_total_amount = 0"
    )
    op.alter_column("website_payment_transactions", "original_total_amount", server_default=None)
    op.alter_column("website_payment_transactions", "discount_percent", server_default=None)
    op.create_index(
        op.f("ix_website_payment_transactions_promo_code"),
        "website_payment_transactions",
        ["promo_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_website_payment_transactions_promo_code"),
        table_name="website_payment_transactions",
    )
    op.drop_column("website_payment_transactions", "promo_code")
    op.drop_column("website_payment_transactions", "discount_percent")
    op.drop_column("website_payment_transactions", "original_total_amount")

    op.drop_index(op.f("ix_promo_codes_created_at"), table_name="promo_codes")
    op.drop_index(op.f("ix_promo_codes_code"), table_name="promo_codes")
    op.drop_table("promo_codes")
