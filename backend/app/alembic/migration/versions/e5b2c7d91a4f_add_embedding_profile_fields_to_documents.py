"""add embedding profile fields to agent documents

Revision ID: e5b2c7d91a4f
Revises: d4f1a8b9c2e3
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b2c7d91a4f"
down_revision: Union[str, Sequence[str], None] = "d4f1a8b9c2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agentdocuments",
        sa.Column("embedding_profile_key", sa.String(length=64), nullable=False, server_default="bge_m3_v1"),
    )
    op.add_column(
        "agentdocuments",
        sa.Column("embedding_schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "agentdocuments",
        sa.Column("embedding_model_name", sa.String(length=128), nullable=False, server_default="BAAI/bge-m3"),
    )
    op.add_column(
        "agentdocuments",
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="1000"),
    )
    op.add_column(
        "agentdocuments",
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="100"),
    )

    op.create_index(
        op.f("ix_agentdocuments_embedding_profile_key"),
        "agentdocuments",
        ["embedding_profile_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agentdocuments_embedding_schema_version"),
        "agentdocuments",
        ["embedding_schema_version"],
        unique=False,
    )
    op.execute("DROP INDEX IF EXISTS uq_agentdocuments_agent_id_content_hash")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agentdocuments_agent_id_content_hash_profile
        ON agentdocuments (agent_id, content_hash, embedding_profile_key)
        WHERE content_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_agentdocuments_agent_id_content_hash_profile")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agentdocuments_agent_id_content_hash
        ON agentdocuments (agent_id, content_hash)
        WHERE content_hash IS NOT NULL
        """
    )

    op.drop_index(op.f("ix_agentdocuments_embedding_schema_version"), table_name="agentdocuments")
    op.drop_index(op.f("ix_agentdocuments_embedding_profile_key"), table_name="agentdocuments")

    op.drop_column("agentdocuments", "chunk_overlap")
    op.drop_column("agentdocuments", "chunk_size")
    op.drop_column("agentdocuments", "embedding_model_name")
    op.drop_column("agentdocuments", "embedding_schema_version")
    op.drop_column("agentdocuments", "embedding_profile_key")

