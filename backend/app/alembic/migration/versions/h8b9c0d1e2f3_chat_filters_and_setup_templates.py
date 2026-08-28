"""chat filters, comment inspect fields and account setup templates

Revision ID: h8b9c0d1e2f3
Revises: g7a8b9c0d1e2
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "h8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "g7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column(
            "account_setup_templates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "chat_import_jobs",
        sa.Column("duplicate_rows", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("chat_targets", sa.Column("members_count", sa.Integer(), nullable=True))
    op.add_column("chat_targets", sa.Column("last_activity_at", sa.DateTime(), nullable=True))
    op.add_column("chat_targets", sa.Column("comments_open", sa.Boolean(), nullable=True))
    op.add_column("chat_targets", sa.Column("comments_checked_at", sa.DateTime(), nullable=True))
    op.add_column("chat_targets", sa.Column("comments_check_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_targets", "comments_check_error")
    op.drop_column("chat_targets", "comments_checked_at")
    op.drop_column("chat_targets", "comments_open")
    op.drop_column("chat_targets", "last_activity_at")
    op.drop_column("chat_targets", "members_count")
    op.drop_column("chat_import_jobs", "duplicate_rows")
    op.drop_column("custom_automations", "account_setup_templates")
