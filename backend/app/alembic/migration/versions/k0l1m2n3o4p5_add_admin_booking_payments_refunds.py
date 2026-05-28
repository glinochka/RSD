"""admin booking payments and manual refund requests

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-05-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k0l1m2n3o4p5"
down_revision: Union[str, Sequence[str], None] = "j9k0l1m2n3o4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_booking_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column(
            "appointment_id",
            sa.Integer(),
            sa.ForeignKey("admin_appointments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("client_external_id", sa.String(length=128), nullable=False),
        sa.Column("yookassa_payment_id", sa.String(length=255), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("booking_payload_json", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','paid','expired','refunded')",
            name="ck_admin_booking_payments_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("yookassa_payment_id", name="uq_admin_booking_payments_yookassa_payment_id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_admin_booking_payments_agent_status",
        "admin_booking_payments",
        ["agent_id", "status"],
    )
    op.create_index(
        "ix_admin_booking_payments_appointment_id",
        "admin_booking_payments",
        ["appointment_id"],
    )
    op.create_index(
        op.f("ix_admin_booking_payments_idempotency_key"),
        "admin_booking_payments",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "admin_booking_refund_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("admin_booking_payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("client_external_id", sa.String(length=128), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="RUB"),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("yookassa_refund_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','refunded','failed')",
            name="ck_admin_booking_refund_requests_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_admin_booking_refund_requests_agent_status",
        "admin_booking_refund_requests",
        ["agent_id", "status"],
    )
    op.create_index(
        op.f("ix_admin_booking_refund_requests_payment_id"),
        "admin_booking_refund_requests",
        ["payment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_booking_refund_requests_payment_id"), table_name="admin_booking_refund_requests")
    op.drop_index("ix_admin_booking_refund_requests_agent_status", table_name="admin_booking_refund_requests")
    op.drop_table("admin_booking_refund_requests")
    op.drop_index(op.f("ix_admin_booking_payments_idempotency_key"), table_name="admin_booking_payments")
    op.drop_index("ix_admin_booking_payments_appointment_id", table_name="admin_booking_payments")
    op.drop_index("ix_admin_booking_payments_agent_status", table_name="admin_booking_payments")
    op.drop_table("admin_booking_payments")
