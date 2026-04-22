"""add user_error_reports table

Revision ID: d0e1f2a3b4c5
Revises: c1d9e3f5a6b7
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c1d9e3f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_error_reports (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_error_reports_user_id
        ON user_error_reports (user_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_error_reports_created_at
        ON user_error_reports (created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_error_reports")
