"""add user auth sessions

Revision ID: b7f3a1d2c9e4
Revises: f1c4d7a9b2e6
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f3a1d2c9e4"
down_revision: Union[str, Sequence[str], None] = "f1c4d7a9b2e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_auth_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index(op.f("ix_user_auth_sessions_user_id"), "user_auth_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_auth_sessions_refresh_token_hash"), "user_auth_sessions", ["refresh_token_hash"], unique=False)
    op.create_index(op.f("ix_user_auth_sessions_expires_at"), "user_auth_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_user_auth_sessions_created_at"), "user_auth_sessions", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_auth_sessions_revoked_at"), "user_auth_sessions", ["revoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_auth_sessions_revoked_at"), table_name="user_auth_sessions")
    op.drop_index(op.f("ix_user_auth_sessions_created_at"), table_name="user_auth_sessions")
    op.drop_index(op.f("ix_user_auth_sessions_expires_at"), table_name="user_auth_sessions")
    op.drop_index(op.f("ix_user_auth_sessions_refresh_token_hash"), table_name="user_auth_sessions")
    op.drop_index(op.f("ix_user_auth_sessions_user_id"), table_name="user_auth_sessions")
    op.drop_table("user_auth_sessions")
