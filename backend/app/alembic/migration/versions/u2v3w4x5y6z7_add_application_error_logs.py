"""add application_error_logs table

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

from alembic import op


revision: str = "u2v3w4x5y6z7"
down_revision: Union[str, Sequence[str], None] = "t1u2v3w4x5y6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS application_error_logs (
            id SERIAL PRIMARY KEY,
            level VARCHAR(20) NOT NULL DEFAULT 'error',
            source VARCHAR(64) NOT NULL DEFAULT 'api',
            scenario VARCHAR(512) NOT NULL,
            error_type VARCHAR(255),
            message TEXT NOT NULL,
            traceback TEXT,
            context_json JSONB,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            status_code INTEGER,
            is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_application_error_logs_user_id
        ON application_error_logs (user_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_application_error_logs_created_at
        ON application_error_logs (created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_application_error_logs_source_created
        ON application_error_logs (source, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_application_error_logs_resolved_created
        ON application_error_logs (is_resolved, created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS application_error_logs")
