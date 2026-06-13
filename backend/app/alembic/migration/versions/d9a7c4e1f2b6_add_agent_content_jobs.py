"""add agent_content_jobs table for content_factory pipeline

Revision ID: d9a7c4e1f2b6
Revises: a4b6c8d1e2f3
Create Date: 2026-04-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9a7c4e1f2b6"
down_revision: Union[str, Sequence[str], None] = "a4b6c8d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_content_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("script_text", sa.Text(), nullable=True),
        sa.Column("script_model", sa.String(length=128), nullable=True),
        sa.Column("kling_task_id", sa.String(length=191), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("youtube_video_id", sa.String(length=191), nullable=True),
        sa.Column("youtube_video_url", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_content_jobs_status_scheduled_for", "agent_content_jobs", ["status", "scheduled_for"], unique=False)
    op.create_index("ix_agent_content_jobs_agent_id", "agent_content_jobs", ["agent_id"], unique=False)
    op.create_index("ix_agent_content_jobs_kling_task_id", "agent_content_jobs", ["kling_task_id"], unique=False)
    op.create_index("ix_agent_content_jobs_youtube_video_id", "agent_content_jobs", ["youtube_video_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_content_jobs_youtube_video_id", table_name="agent_content_jobs")
    op.drop_index("ix_agent_content_jobs_kling_task_id", table_name="agent_content_jobs")
    op.drop_index("ix_agent_content_jobs_agent_id", table_name="agent_content_jobs")
    op.drop_index("ix_agent_content_jobs_status_scheduled_for", table_name="agent_content_jobs")
    op.drop_table("agent_content_jobs")
