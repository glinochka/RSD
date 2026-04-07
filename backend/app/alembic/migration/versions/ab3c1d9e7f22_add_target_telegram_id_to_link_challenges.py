"""add target_telegram_id to telegram link challenges

Revision ID: ab3c1d9e7f22
Revises: 9c4a2c8b5f11
Create Date: 2026-03-31
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ab3c1d9e7f22"
down_revision: Union[str, Sequence[str], None] = "9c4a2c8b5f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safe for databases where the column may already exist.
    op.execute(
        """
        ALTER TABLE telegram_link_challenges
        ADD COLUMN IF NOT EXISTS target_telegram_id BIGINT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_telegram_link_challenges_target_telegram_id
        ON telegram_link_challenges (target_telegram_id)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_telegram_link_challenges_target_telegram_id
        """
    )
    op.execute(
        """
        ALTER TABLE telegram_link_challenges
        DROP COLUMN IF EXISTS target_telegram_id
        """
    )
