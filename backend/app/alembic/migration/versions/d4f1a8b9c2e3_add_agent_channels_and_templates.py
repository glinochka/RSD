"""add multi-channel foundation tables and agent template fields

Revision ID: d4f1a8b9c2e3
Revises: c8e9f0a1b2c3
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f1a8b9c2e3"
down_revision: Union[str, Sequence[str], None] = "c8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "primary_provider",
            sa.String(length=32),
            nullable=False,
            server_default="telegram_bot",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "template_type",
            sa.String(length=32),
            nullable=False,
            server_default="qa",
        ),
    )
    op.add_column("agents", sa.Column("template_config", sa.Text(), nullable=True))

    op.create_table(
        "agent_channel_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("connection_type", sa.String(length=32), nullable=False, server_default="bot"),
        sa.Column("external_id", sa.String(length=191), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_id", name="uq_agent_channel_provider_external"),
    )
    op.create_index(
        op.f("ix_agent_channel_connections_agent_id"),
        "agent_channel_connections",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_channel_connections_provider"),
        "agent_channel_connections",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_channel_connections_external_id"),
        "agent_channel_connections",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_channel_connections_created_at"),
        "agent_channel_connections",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "user_external_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_user_id", sa.String(length=191), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_user_id", name="uq_user_identity_provider_external"),
    )
    op.create_index(
        op.f("ix_user_external_identities_user_id"),
        "user_external_identities",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_external_identities_provider"),
        "user_external_identities",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_external_identities_external_user_id"),
        "user_external_identities",
        ["external_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_external_identities_created_at"),
        "user_external_identities",
        ["created_at"],
        unique=False,
    )

    # Backfill existing Telegram bot agents into new generalized channel connections.
    op.execute(
        sa.text(
            """
            INSERT INTO agent_channel_connections
            (agent_id, provider, connection_type, external_id, encrypted_credentials, is_primary, is_active, created_at, updated_at)
            SELECT
                id,
                'telegram_bot',
                'bot',
                CAST(bot_id AS VARCHAR(191)),
                encrypted_token,
                true,
                COALESCE(is_active, false),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM agents
            WHERE bot_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_external_identities_created_at"), table_name="user_external_identities")
    op.drop_index(op.f("ix_user_external_identities_external_user_id"), table_name="user_external_identities")
    op.drop_index(op.f("ix_user_external_identities_provider"), table_name="user_external_identities")
    op.drop_index(op.f("ix_user_external_identities_user_id"), table_name="user_external_identities")
    op.drop_table("user_external_identities")

    op.drop_index(op.f("ix_agent_channel_connections_created_at"), table_name="agent_channel_connections")
    op.drop_index(op.f("ix_agent_channel_connections_external_id"), table_name="agent_channel_connections")
    op.drop_index(op.f("ix_agent_channel_connections_provider"), table_name="agent_channel_connections")
    op.drop_index(op.f("ix_agent_channel_connections_agent_id"), table_name="agent_channel_connections")
    op.drop_table("agent_channel_connections")

    op.drop_column("agents", "template_config")
    op.drop_column("agents", "template_type")
    op.drop_column("agents", "primary_provider")

