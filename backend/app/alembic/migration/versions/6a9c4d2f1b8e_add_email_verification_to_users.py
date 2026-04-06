"""add email verification to users

Revision ID: 6a9c4d2f1b8e
Revises: b7f3a1d2c9e4
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a9c4d2f1b8e"
down_revision: Union[str, Sequence[str], None] = "b7f3a1d2c9e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("email_verification_code_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verification_attempts_left", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "email_verification_attempts_left")
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_code_hash")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
