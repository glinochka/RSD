"""add admin_applications table for application intake workflow

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "x4y5z6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("client_external_id", sa.String(length=128), nullable=False),
        sa.Column("client_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="new"),
        sa.Column("fields_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("source_channel", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('new','in_progress','completed','rejected','cancelled')",
            name="ck_admin_applications_status",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_applications_agent_id", "admin_applications", ["agent_id"], unique=False)
    op.create_index("ix_admin_applications_status", "admin_applications", ["status"], unique=False)
    op.create_index("ix_admin_applications_created_at", "admin_applications", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_applications_agent_status_created",
        "admin_applications",
        ["agent_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_applications_client_lookup",
        "admin_applications",
        ["agent_id", "client_external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_applications_client_lookup", table_name="admin_applications")
    op.drop_index("ix_admin_applications_agent_status_created", table_name="admin_applications")
    op.drop_index("ix_admin_applications_created_at", table_name="admin_applications")
    op.drop_index("ix_admin_applications_status", table_name="admin_applications")
    op.drop_index("ix_admin_applications_agent_id", table_name="admin_applications")
    op.drop_table("admin_applications")
