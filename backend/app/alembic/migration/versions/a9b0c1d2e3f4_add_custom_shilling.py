"""add custom shilling module

Revision ID: a9b0c1d2e3f4
Revises: z7a8b9c0d1e2
Create Date: 2026-08-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "z7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column(
            "is_shilling_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "chat_targets",
        sa.Column(
            "shilling_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_targets", "shilling_config")
    op.drop_column("custom_automations", "is_shilling_enabled")
