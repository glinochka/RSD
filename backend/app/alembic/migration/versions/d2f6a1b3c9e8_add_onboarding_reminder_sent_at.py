"""add onboarding_reminder_sent_at to users

Revision ID: d2f6a1b3c9e8
Revises: a9f1d2e3c4b5
Create Date: 2026-05-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f6a1b3c9e8"
down_revision: Union[str, Sequence[str], None] = "a9f1d2e3c4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarding_reminder_sent_at", sa.DateTime(), nullable=True))
    op.create_index(
        op.f("ix_users_onboarding_reminder_sent_at"),
        "users",
        ["onboarding_reminder_sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_onboarding_reminder_sent_at"), table_name="users")
    op.drop_column("users", "onboarding_reminder_sent_at")
