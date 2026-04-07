"""add password reset fields to users

Revision ID: d8f1a2c3b4e5
Revises: c4e8b1a0d2f3
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8f1a2c3b4e5"
down_revision: Union[str, Sequence[str], None] = "c4e8b1a0d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_code_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("password_reset_attempts_left", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("password_reset_last_sent_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("password_reset_verified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_reset_verified_at")
    op.drop_column("users", "password_reset_token_hash")
    op.drop_column("users", "password_reset_last_sent_at")
    op.drop_column("users", "password_reset_attempts_left")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_code_hash")
