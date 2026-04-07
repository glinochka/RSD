"""add agent_frozen_users table

Revision ID: c8e9f0a1b2c3
Revises: a7d1e2c9f4b0
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "a7d1e2c9f4b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_frozen_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_external_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "user_external_id", name="uq_agent_frozen_user_external"),
    )
    op.create_index(
        op.f("ix_agent_frozen_users_agent_id"),
        "agent_frozen_users",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_frozen_users_user_external_id"),
        "agent_frozen_users",
        ["user_external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_frozen_users_user_external_id"), table_name="agent_frozen_users")
    op.drop_index(op.f("ix_agent_frozen_users_agent_id"), table_name="agent_frozen_users")
    op.drop_table("agent_frozen_users")
