"""add telegram link challenges

Revision ID: 9c4a2c8b5f11
Revises: f2b7a9c41e11
Create Date: 2026-03-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4a2c8b5f11"
down_revision: Union[str, Sequence[str], None] = "f2b7a9c41e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_link_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts_left", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_telegram_link_challenges_user_id"),
        "telegram_link_challenges",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telegram_link_challenges_code_hash"),
        "telegram_link_challenges",
        ["code_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telegram_link_challenges_expires_at"),
        "telegram_link_challenges",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_link_challenges_expires_at"), table_name="telegram_link_challenges")
    op.drop_index(op.f("ix_telegram_link_challenges_code_hash"), table_name="telegram_link_challenges")
    op.drop_index(op.f("ix_telegram_link_challenges_user_id"), table_name="telegram_link_challenges")
    op.drop_table("telegram_link_challenges")
