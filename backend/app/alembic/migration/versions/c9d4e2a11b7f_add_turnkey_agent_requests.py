"""add turnkey agent requests table

Revision ID: c9d4e2a11b7f
Revises: ab3c1d9e7f22
Create Date: 2026-04-02
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9d4e2a11b7f"
down_revision: Union[str, Sequence[str], None] = "ab3c1d9e7f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS turnkey_agent_requests (
            id SERIAL PRIMARY KEY,
            phone_number VARCHAR(32) NOT NULL,
            email VARCHAR(255) NOT NULL,
            requested_agent VARCHAR(255) NOT NULL,
            purpose TEXT NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_turnkey_agent_requests_phone_number
        ON turnkey_agent_requests (phone_number)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_turnkey_agent_requests_email
        ON turnkey_agent_requests (email)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_turnkey_agent_requests_created_at
        ON turnkey_agent_requests (created_at)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS turnkey_agent_requests
        """
    )
