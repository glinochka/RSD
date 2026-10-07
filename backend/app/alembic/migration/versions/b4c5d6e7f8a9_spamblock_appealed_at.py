"""Track last @SpamBot appeal so health checks do not hammer the bot.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("spamblock_appealed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("social_accounts", "spamblock_appealed_at")
