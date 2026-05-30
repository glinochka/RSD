"""admin refund request contact and appointment snapshot fields

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-05-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_booking_refund_requests",
        sa.Column("client_full_name", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "admin_booking_refund_requests",
        sa.Column("client_phone", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "admin_booking_refund_requests",
        sa.Column("source_channel", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "admin_booking_refund_requests",
        sa.Column("appointment_starts_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "admin_booking_refund_requests",
        sa.Column("service_title", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "admin_booking_refund_requests",
        sa.Column("refund_mode", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("admin_booking_refund_requests", "refund_mode")
    op.drop_column("admin_booking_refund_requests", "service_title")
    op.drop_column("admin_booking_refund_requests", "appointment_starts_at")
    op.drop_column("admin_booking_refund_requests", "source_channel")
    op.drop_column("admin_booking_refund_requests", "client_phone")
    op.drop_column("admin_booking_refund_requests", "client_full_name")
