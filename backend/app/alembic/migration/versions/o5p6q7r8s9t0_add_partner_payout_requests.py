"""add partner payout requests

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, Sequence[str], None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partner_payout_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partner_user_id", sa.Integer(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("payment_details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["partner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_partner_payout_requests_partner_user_id"),
        "partner_payout_requests",
        ["partner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_payout_requests_status"),
        "partner_payout_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_payout_requests_created_at"),
        "partner_payout_requests",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_payout_requests_created_at"), table_name="partner_payout_requests")
    op.drop_index(op.f("ix_partner_payout_requests_status"), table_name="partner_payout_requests")
    op.drop_index(op.f("ix_partner_payout_requests_partner_user_id"), table_name="partner_payout_requests")
    op.drop_table("partner_payout_requests")
