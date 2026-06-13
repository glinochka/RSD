"""add staff_id to admin_services

Revision ID: c2e5a7b8d9f1
Revises: b74f2d1a9c31
Create Date: 2026-04-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2e5a7b8d9f1"
down_revision: Union[str, Sequence[str], None] = "b74f2d1a9c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_services",
        sa.Column(
            "staff_id",
            sa.Integer(),
            sa.ForeignKey("admin_staff.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_admin_services_staff_id",
        "admin_services",
        ["staff_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_services_staff_id", table_name="admin_services")
    op.drop_column("admin_services", "staff_id")
