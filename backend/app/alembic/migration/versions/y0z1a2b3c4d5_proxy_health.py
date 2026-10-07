"""Track proxy liveness for safe session rotation.

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y0z1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "x9y0z1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_proxies",
        sa.Column("is_healthy", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "custom_proxies",
        sa.Column("fail_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("custom_proxies", sa.Column("last_ok_at", sa.DateTime(), nullable=True))
    op.add_column("custom_proxies", sa.Column("last_failed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_custom_proxies_is_healthy", "custom_proxies", ["is_healthy"])


def downgrade() -> None:
    op.drop_index("ix_custom_proxies_is_healthy", table_name="custom_proxies")
    op.drop_column("custom_proxies", "last_failed_at")
    op.drop_column("custom_proxies", "last_ok_at")
    op.drop_column("custom_proxies", "fail_count")
    op.drop_column("custom_proxies", "is_healthy")
