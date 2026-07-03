"""add project integrations, external events and checklist_hidden flag

Revision ID: a1b2c3d4e5f6
Revises: z6a7b8c9d0e1
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "z6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dashboard checklist preference
    op.add_column(
        "projects",
        sa.Column("checklist_hidden", sa.Boolean(), server_default="false", nullable=False),
    )

    # Project integrations table
    op.create_table(
        "project_integrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default="'{}'::jsonb", nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("webhook_token", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_integrations_project_id", "project_integrations", ["project_id"], unique=False)
    op.create_index("ix_project_integrations_type", "project_integrations", ["type"], unique=False)
    op.create_index("ix_project_integrations_is_active", "project_integrations", ["is_active"], unique=False)
    op.create_index("ix_project_integrations_webhook_token", "project_integrations", ["webhook_token"], unique=True)

    # External events received from integrations
    op.create_table(
        "project_external_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="'{}'::jsonb", nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["project_integrations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_external_events_project_id", "project_external_events", ["project_id"], unique=False)
    op.create_index("ix_project_external_events_created_at", "project_external_events", ["created_at"], unique=False)
    op.create_index("ix_project_external_events_event_type", "project_external_events", ["event_type"], unique=False)
    op.create_index("ix_project_external_events_integration_id", "project_external_events", ["integration_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_external_events_integration_id", table_name="project_external_events")
    op.drop_index("ix_project_external_events_event_type", table_name="project_external_events")
    op.drop_index("ix_project_external_events_created_at", table_name="project_external_events")
    op.drop_index("ix_project_external_events_project_id", table_name="project_external_events")
    op.drop_table("project_external_events")

    op.drop_index("ix_project_integrations_webhook_token", table_name="project_integrations")
    op.drop_index("ix_project_integrations_is_active", table_name="project_integrations")
    op.drop_index("ix_project_integrations_type", table_name="project_integrations")
    op.drop_index("ix_project_integrations_project_id", table_name="project_integrations")
    op.drop_table("project_integrations")

    op.drop_column("projects", "checklist_hidden")
