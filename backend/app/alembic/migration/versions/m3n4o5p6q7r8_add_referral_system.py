"""add referral system tables and user fields

Revision ID: m3n4o5p6q7r8
Revises: l1m2n3o4p5q6r7
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, Sequence[str], None] = "l1m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("referred_by_user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_referral_code"), "users", ["referral_code"], unique=True)
    op.create_index(op.f("ix_users_referred_by_user_id"), "users", ["referred_by_user_id"], unique=False)
    op.create_foreign_key(
        "fk_users_referred_by_user_id_users",
        "users",
        "users",
        ["referred_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("website_payment_transactions", sa.Column("partner_user_id", sa.Integer(), nullable=True))
    op.add_column(
        "website_payment_transactions",
        sa.Column("partner_promo_discount_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        op.f("ix_website_payment_transactions_partner_user_id"),
        "website_payment_transactions",
        ["partner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_website_payment_transactions_partner_user_id_users",
        "website_payment_transactions",
        "users",
        ["partner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("website_payment_transactions", "partner_promo_discount_percent", server_default=None)

    op.create_table(
        "partner_promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partner_user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["partner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partner_user_id", "code", name="uq_partner_promo_codes_partner_code"),
    )
    op.create_index(
        op.f("ix_partner_promo_codes_partner_user_id"),
        "partner_promo_codes",
        ["partner_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_partner_promo_codes_code"), "partner_promo_codes", ["code"], unique=False)
    op.create_index(
        op.f("ix_partner_promo_codes_created_at"),
        "partner_promo_codes",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "referral_commissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partner_user_id", sa.Integer(), nullable=False),
        sa.Column("buyer_user_id", sa.Integer(), nullable=False),
        sa.Column("website_payment_transaction_id", sa.Integer(), nullable=False),
        sa.Column("gross_amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("commission_percent", sa.Integer(), nullable=False),
        sa.Column("commission_amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("promo_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["website_payment_transaction_id"],
            ["website_payment_transactions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "website_payment_transaction_id",
            name="uq_referral_commissions_website_payment_tx",
        ),
    )
    op.create_index(
        op.f("ix_referral_commissions_partner_user_id"),
        "referral_commissions",
        ["partner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_referral_commissions_buyer_user_id"),
        "referral_commissions",
        ["buyer_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_referral_commissions_website_payment_transaction_id"),
        "referral_commissions",
        ["website_payment_transaction_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_referral_commissions_created_at"),
        "referral_commissions",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_referral_commissions_created_at"), table_name="referral_commissions")
    op.drop_index(
        op.f("ix_referral_commissions_website_payment_transaction_id"),
        table_name="referral_commissions",
    )
    op.drop_index(op.f("ix_referral_commissions_buyer_user_id"), table_name="referral_commissions")
    op.drop_index(op.f("ix_referral_commissions_partner_user_id"), table_name="referral_commissions")
    op.drop_table("referral_commissions")

    op.drop_index(op.f("ix_partner_promo_codes_created_at"), table_name="partner_promo_codes")
    op.drop_index(op.f("ix_partner_promo_codes_code"), table_name="partner_promo_codes")
    op.drop_index(op.f("ix_partner_promo_codes_partner_user_id"), table_name="partner_promo_codes")
    op.drop_table("partner_promo_codes")

    op.drop_constraint(
        "fk_website_payment_transactions_partner_user_id_users",
        "website_payment_transactions",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_website_payment_transactions_partner_user_id"),
        table_name="website_payment_transactions",
    )
    op.drop_column("website_payment_transactions", "partner_promo_discount_percent")
    op.drop_column("website_payment_transactions", "partner_user_id")

    op.drop_constraint("fk_users_referred_by_user_id_users", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_referred_by_user_id"), table_name="users")
    op.drop_index(op.f("ix_users_referral_code"), table_name="users")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
