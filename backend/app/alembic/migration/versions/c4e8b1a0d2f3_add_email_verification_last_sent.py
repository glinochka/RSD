"""add email_verification_last_sent_at to users

Revision ID: c4e8b1a0d2f3
Revises: 6a9c4d2f1b8e
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8b1a0d2f3"
down_revision: Union[str, Sequence[str], None] = "6a9c4d2f1b8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verification_last_sent_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verification_last_sent_at")
