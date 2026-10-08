"""Account restriction kinds and session auto-guard.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("restriction_kind", sa.String(length=32), nullable=True))
    op.add_column("social_accounts", sa.Column("restriction_until", sa.DateTime(), nullable=True))
    op.add_column("social_accounts", sa.Column("restriction_detail", sa.Text(), nullable=True))
    op.add_column(
        "social_accounts",
        sa.Column("session_guard_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("social_accounts", sa.Column("session_guard_paused_until", sa.DateTime(), nullable=True))
    op.add_column("social_accounts", sa.Column("session_guard_checked_at", sa.DateTime(), nullable=True))
    op.add_column("social_accounts", sa.Column("known_auth_hashes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("social_accounts", "known_auth_hashes")
    op.drop_column("social_accounts", "session_guard_checked_at")
    op.drop_column("social_accounts", "session_guard_paused_until")
    op.drop_column("social_accounts", "session_guard_enabled")
    op.drop_column("social_accounts", "restriction_detail")
    op.drop_column("social_accounts", "restriction_until")
    op.drop_column("social_accounts", "restriction_kind")
