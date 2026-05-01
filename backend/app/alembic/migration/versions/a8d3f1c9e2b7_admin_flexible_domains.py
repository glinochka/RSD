"""admin flexible domains: drop role check constraints, expand varchar, add linked_staff_id

Revision ID: a8d3f1c9e2b7
Revises: f0a1b2c3d4e5
Create Date: 2026-05-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8d3f1c9e2b7"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop CHECK constraint on admin_staff.role
    op.drop_constraint("ck_admin_staff_role", "admin_staff", type_="check")

    # Expand admin_staff.role from VARCHAR(16) to VARCHAR(32)
    op.alter_column(
        "admin_staff",
        "role",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )

    # Drop CHECK constraint on admin_resources.resource_type
    op.drop_constraint("ck_admin_resources_type", "admin_resources", type_="check")

    # Expand admin_resources.resource_type from VARCHAR(16) to VARCHAR(32)
    op.alter_column(
        "admin_resources",
        "resource_type",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )

    # Add linked_staff_id to admin_resources (nullable FK → admin_staff.id)
    op.add_column(
        "admin_resources",
        sa.Column("linked_staff_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_admin_resources_linked_staff",
        "admin_resources",
        "admin_staff",
        ["linked_staff_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_admin_resources_linked_staff_id",
        "admin_resources",
        ["linked_staff_id"],
        unique=False,
    )

    # Expand admin_services.target_role from VARCHAR(16) to VARCHAR(32)
    op.alter_column(
        "admin_services",
        "target_role",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_resources_linked_staff_id", table_name="admin_resources")
    op.drop_constraint("fk_admin_resources_linked_staff", "admin_resources", type_="foreignkey")
    op.drop_column("admin_resources", "linked_staff_id")

    op.alter_column(
        "admin_services",
        "target_role",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )

    op.alter_column(
        "admin_resources",
        "resource_type",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_admin_resources_type",
        "admin_resources",
        "resource_type IN ('chair','room','equipment')",
    )

    op.alter_column(
        "admin_staff",
        "role",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_admin_staff_role",
        "admin_staff",
        "role IN ('master','doctor')",
    )
