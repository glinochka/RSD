"""Unified custom automation jobs for the Tasks UI.

Revision ID: u6v7w8x9y0z1
Revises: t4u5v6w7x8y9
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "u6v7w8x9y0z1"
down_revision: Union[str, Sequence[str], None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("logs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_custom_jobs_automation", "custom_jobs", ["custom_automation_id"])
    op.create_index("ix_custom_jobs_status", "custom_jobs", ["status"])
    op.create_index("ix_custom_jobs_category", "custom_jobs", ["category"])
    op.create_index("ix_custom_jobs_type", "custom_jobs", ["job_type"])
    op.create_index("ix_custom_jobs_created", "custom_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_custom_jobs_created", table_name="custom_jobs")
    op.drop_index("ix_custom_jobs_type", table_name="custom_jobs")
    op.drop_index("ix_custom_jobs_category", table_name="custom_jobs")
    op.drop_index("ix_custom_jobs_status", table_name="custom_jobs")
    op.drop_index("ix_custom_jobs_automation", table_name="custom_jobs")
    op.drop_table("custom_jobs")
