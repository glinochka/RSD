"""allow same service title per staff on admin_services

Revision ID: a1b2c3d4e5f6
Revises: f9a0b1c2d3e4
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_admin_services_agent_title", "admin_services", type_="unique")
    op.create_index(
        "uq_admin_services_agent_title_staff",
        "admin_services",
        ["agent_id", "title", "staff_id"],
        unique=True,
        postgresql_where=sa.text("staff_id IS NOT NULL"),
    )
    op.create_index(
        "uq_admin_services_agent_title_general",
        "admin_services",
        ["agent_id", "title"],
        unique=True,
        postgresql_where=sa.text("staff_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_admin_services_agent_title_general", table_name="admin_services")
    op.drop_index("uq_admin_services_agent_title_staff", table_name="admin_services")
    op.create_unique_constraint(
        "uq_admin_services_agent_title",
        "admin_services",
        ["agent_id", "title"],
    )
