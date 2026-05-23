"""add telephony_sip_routes (SIP trunk routing 7C)

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = "g6h7i8j9k0l1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telephony_sip_routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("match_from", sa.String(length=128), nullable=True),
        sa.Column("match_to", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["connection_id"], ["agent_channel_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_telephony_sip_routes_connection_id"),
        "telephony_sip_routes",
        ["connection_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_telephony_sip_routes_connection_id"), table_name="telephony_sip_routes")
    op.drop_table("telephony_sip_routes")
