"""add reindex jobs table

Revision ID: f1c4d7a9b2e6
Revises: e5b2c7d91a4f
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1c4d7a9b2e6"
down_revision: Union[str, Sequence[str], None] = "e5b2c7d91a4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reindex_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("target_embedding_profile_key", sa.String(length=64), nullable=False),
        sa.Column("target_embedding_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("target_embedding_model_name", sa.String(length=128), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("document_cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reindex_jobs_agent_id"), "reindex_jobs", ["agent_id"], unique=False)
    op.create_index(op.f("ix_reindex_jobs_requested_by_user_id"), "reindex_jobs", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_reindex_jobs_status"), "reindex_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_reindex_jobs_target_embedding_profile_key"), "reindex_jobs", ["target_embedding_profile_key"], unique=False)
    op.create_index(op.f("ix_reindex_jobs_created_at"), "reindex_jobs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reindex_jobs_created_at"), table_name="reindex_jobs")
    op.drop_index(op.f("ix_reindex_jobs_target_embedding_profile_key"), table_name="reindex_jobs")
    op.drop_index(op.f("ix_reindex_jobs_status"), table_name="reindex_jobs")
    op.drop_index(op.f("ix_reindex_jobs_requested_by_user_id"), table_name="reindex_jobs")
    op.drop_index(op.f("ix_reindex_jobs_agent_id"), table_name="reindex_jobs")
    op.drop_table("reindex_jobs")

