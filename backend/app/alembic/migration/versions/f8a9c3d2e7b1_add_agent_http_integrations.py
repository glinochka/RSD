"""Add agent_http_integrations for configurable external HTTP/API tools."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a9c3d2e7b1"
down_revision: Union[str, Sequence[str], None] = "6d25ccf959ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_http_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("encrypted_config", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "name", name="uq_agent_http_integrations_agent_name"),
    )
    op.create_index(
        op.f("ix_agent_http_integrations_agent_id"),
        "agent_http_integrations",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_http_integrations_name"),
        "agent_http_integrations",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_http_integrations_name"), table_name="agent_http_integrations")
    op.drop_index(op.f("ix_agent_http_integrations_agent_id"), table_name="agent_http_integrations")
    op.drop_table("agent_http_integrations")
