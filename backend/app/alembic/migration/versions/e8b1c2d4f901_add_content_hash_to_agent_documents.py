"""add content hash to agent documents

Revision ID: e8b1c2d4f901
Revises: c9d4e2a11b7f
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8b1c2d4f901"
down_revision: Union[str, Sequence[str], None] = "c9d4e2a11b7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE agentdocuments
        ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agentdocuments_content_hash
        ON agentdocuments (content_hash)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agentdocuments_agent_id_content_hash
        ON agentdocuments (agent_id, content_hash)
        WHERE content_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS uq_agentdocuments_agent_id_content_hash
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS ix_agentdocuments_content_hash
        """
    )
    op.execute(
        """
        ALTER TABLE agentdocuments
        DROP COLUMN IF EXISTS content_hash
        """
    )
