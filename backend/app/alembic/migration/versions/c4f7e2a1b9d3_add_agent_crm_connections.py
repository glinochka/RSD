"""add agent crm connections table

Revision ID: c4f7e2a1b9d3
Revises: b3e7d9a1c4f2
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f7e2a1b9d3"
down_revision: Union[str, Sequence[str], None] = "b3e7d9a1c4f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_crm_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=191), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "provider", name="uq_agent_crm_agent_provider"),
        sa.UniqueConstraint("provider", "external_id", name="uq_agent_crm_provider_external"),
    )
    op.create_index(op.f("ix_agent_crm_connections_agent_id"), "agent_crm_connections", ["agent_id"], unique=False)
    op.create_index(op.f("ix_agent_crm_connections_provider"), "agent_crm_connections", ["provider"], unique=False)
    op.create_index(op.f("ix_agent_crm_connections_external_id"), "agent_crm_connections", ["external_id"], unique=False)
    op.create_index(op.f("ix_agent_crm_connections_created_at"), "agent_crm_connections", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_crm_connections_created_at"), table_name="agent_crm_connections")
    op.drop_index(op.f("ix_agent_crm_connections_external_id"), table_name="agent_crm_connections")
    op.drop_index(op.f("ix_agent_crm_connections_provider"), table_name="agent_crm_connections")
    op.drop_index(op.f("ix_agent_crm_connections_agent_id"), table_name="agent_crm_connections")
    op.drop_table("agent_crm_connections")
