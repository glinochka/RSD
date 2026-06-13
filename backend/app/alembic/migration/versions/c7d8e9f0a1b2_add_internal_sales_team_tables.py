"""add internal sales team and outbound contacts tables

Revision ID: c7d8e9f0a1b2
Revises: f8a9c3d2e7b1
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "f8a9c3d2e7b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_team_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("supervisor_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("plan_calls_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_demos_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_closes_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_contacts_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('trainee','mop','rop')", name="ck_sales_team_members_role"),
        sa.ForeignKeyConstraint(["supervisor_id"], ["sales_team_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_team_members_login", "sales_team_members", ["login"], unique=True)
    op.create_index("ix_sales_team_members_role", "sales_team_members", ["role"], unique=False)
    op.create_index("ix_sales_team_members_created_at", "sales_team_members", ["created_at"], unique=False)
    op.create_index(op.f("ix_sales_team_members_supervisor_id"), "sales_team_members", ["supervisor_id"], unique=False)

    op.create_table(
        "sales_outbound_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=False),
        sa.Column("funnel_stage", sa.String(length=16), nullable=False, server_default="in_base"),
        sa.Column("label", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column("called_at", sa.DateTime(), nullable=True),
        sa.Column("demo_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "funnel_stage IN ('in_base','called','demo','closed')",
            name="ck_sales_outbound_contacts_stage",
        ),
        sa.ForeignKeyConstraint(["assignee_id"], ["sales_team_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_outbound_contacts_assignee", "sales_outbound_contacts", ["assignee_id"], unique=False)
    op.create_index("ix_sales_outbound_contacts_stage", "sales_outbound_contacts", ["funnel_stage"], unique=False)
    op.create_index("ix_sales_outbound_contacts_created_at", "sales_outbound_contacts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sales_outbound_contacts_created_at", table_name="sales_outbound_contacts")
    op.drop_index("ix_sales_outbound_contacts_stage", table_name="sales_outbound_contacts")
    op.drop_index("ix_sales_outbound_contacts_assignee", table_name="sales_outbound_contacts")
    op.drop_table("sales_outbound_contacts")
    op.drop_index(op.f("ix_sales_team_members_supervisor_id"), table_name="sales_team_members")
    op.drop_index("ix_sales_team_members_created_at", table_name="sales_team_members")
    op.drop_index("ix_sales_team_members_role", table_name="sales_team_members")
    op.drop_index("ix_sales_team_members_login", table_name="sales_team_members")
    op.drop_table("sales_team_members")
