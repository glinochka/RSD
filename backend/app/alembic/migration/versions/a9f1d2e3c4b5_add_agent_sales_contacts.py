"""add agent_sales_contacts table

Revision ID: a9f1d2e3c4b5
Revises: f7a3c9e2b8d1
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9f1d2e3c4b5"
down_revision: Union[str, Sequence[str], None] = "f7a3c9e2b8d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sales_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_external_id", sa.String(length=128), nullable=False),
        sa.Column("source_chat_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="DISCOVERED"),
        sa.Column("last_contacted_at", sa.DateTime(), nullable=True),
        sa.Column("last_reason", sa.String(length=128), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "user_external_id", "source_chat_id", name="uq_agent_sales_contact_key"),
    )
    op.create_index(op.f("ix_agent_sales_contacts_agent_id"), "agent_sales_contacts", ["agent_id"], unique=False)
    op.create_index(
        op.f("ix_agent_sales_contacts_user_external_id"),
        "agent_sales_contacts",
        ["user_external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_sales_contacts_source_chat_id"),
        "agent_sales_contacts",
        ["source_chat_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_sales_contacts_state"), "agent_sales_contacts", ["state"], unique=False)
    op.create_index(op.f("ix_agent_sales_contacts_created_at"), "agent_sales_contacts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_sales_contacts_created_at"), table_name="agent_sales_contacts")
    op.drop_index(op.f("ix_agent_sales_contacts_state"), table_name="agent_sales_contacts")
    op.drop_index(op.f("ix_agent_sales_contacts_source_chat_id"), table_name="agent_sales_contacts")
    op.drop_index(op.f("ix_agent_sales_contacts_user_external_id"), table_name="agent_sales_contacts")
    op.drop_index(op.f("ix_agent_sales_contacts_agent_id"), table_name="agent_sales_contacts")
    op.drop_table("agent_sales_contacts")

