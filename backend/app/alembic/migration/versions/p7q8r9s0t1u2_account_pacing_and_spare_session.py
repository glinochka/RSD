"""account rest, delayed retries, spare telegram session

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, Sequence[str], None] = "o6p7q8r9s0t1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("next_action_at", sa.DateTime(), nullable=True))
    op.add_column("social_accounts", sa.Column("encrypted_spare_session", sa.Text(), nullable=True))
    op.add_column("social_accounts", sa.Column("spare_session_file_path", sa.String(length=512), nullable=True))
    op.add_column("social_accounts", sa.Column("spare_authorization_hash", sa.BigInteger(), nullable=True))
    op.add_column("social_accounts", sa.Column("sessions_pruned_at", sa.DateTime(), nullable=True))
    op.create_index("ix_social_accounts_next_action_at", "social_accounts", ["next_action_at"])
    op.add_column("pending_chat_actions", sa.Column("next_attempt_at", sa.DateTime(), nullable=True))
    op.create_index("ix_pending_chat_actions_next_attempt_at", "pending_chat_actions", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_pending_chat_actions_next_attempt_at", table_name="pending_chat_actions")
    op.drop_column("pending_chat_actions", "next_attempt_at")
    op.drop_index("ix_social_accounts_next_action_at", table_name="social_accounts")
    op.drop_column("social_accounts", "sessions_pruned_at")
    op.drop_column("social_accounts", "spare_authorization_hash")
    op.drop_column("social_accounts", "spare_session_file_path")
    op.drop_column("social_accounts", "encrypted_spare_session")
    op.drop_column("social_accounts", "next_action_at")
