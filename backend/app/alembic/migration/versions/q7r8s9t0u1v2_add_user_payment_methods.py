"""add user saved payment methods

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-05-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_payment_methods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("yookassa_payment_method_id", sa.String(length=64), nullable=False),
        sa.Column("card_type", sa.String(length=32), nullable=True),
        sa.Column("card_last4", sa.String(length=4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "yookassa_payment_method_id",
            name="uq_user_payment_methods_user_method",
        ),
    )
    op.create_index(
        op.f("ix_user_payment_methods_user_id"),
        "user_payment_methods",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_payment_methods_yookassa_payment_method_id"),
        "user_payment_methods",
        ["yookassa_payment_method_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_payment_methods_yookassa_payment_method_id"),
        table_name="user_payment_methods",
    )
    op.drop_index(op.f("ix_user_payment_methods_user_id"), table_name="user_payment_methods")
    op.drop_table("user_payment_methods")
