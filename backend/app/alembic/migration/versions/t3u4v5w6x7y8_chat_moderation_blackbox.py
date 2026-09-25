"""Chat moderation black box columns on chat_targets.

Adds:
  - chat_targets.mod_status          (untested | no_moderation | moderated)
  - chat_targets.mod_consecutive_removed
  - chat_targets.mod_consecutive_kept
  - chat_targets.mod_checked_at
  - chat_targets.black_boxed_at
  - chat_targets.max_daily_target_actions (int, default 3)

Revision ID: t3u4v5w6x7y8
Revises: a0b1c2d3e4f5
Create Date: 2026-09-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "t3u4v5w6x7y8"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_targets", sa.Column("mod_status", sa.String(length=32), server_default=sa.text("'untested'"), nullable=False))
    op.add_column("chat_targets", sa.Column("mod_consecutive_removed", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("chat_targets", sa.Column("mod_consecutive_kept", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("chat_targets", sa.Column("mod_checked_at", sa.DateTime(), nullable=True))
    op.add_column("chat_targets", sa.Column("black_boxed_at", sa.DateTime(), nullable=True))
    op.add_column("chat_targets", sa.Column("max_daily_target_actions", sa.Integer(), server_default=sa.text("3"), nullable=False))
    op.create_index("ix_chat_targets_mod_status", "chat_targets", ["mod_status"])
    op.create_index("ix_chat_targets_black_boxed_at", "chat_targets", ["black_boxed_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_targets_black_boxed_at", table_name="chat_targets")
    op.drop_index("ix_chat_targets_mod_status", table_name="chat_targets")
    op.drop_column("chat_targets", "max_daily_target_actions")
    op.drop_column("chat_targets", "black_boxed_at")
    op.drop_column("chat_targets", "mod_checked_at")
    op.drop_column("chat_targets", "mod_consecutive_kept")
    op.drop_column("chat_targets", "mod_consecutive_removed")
    op.drop_column("chat_targets", "mod_status")
