"""dedicated per-account proxies

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r9s0t1u2v3w4"
down_revision: Union[str, Sequence[str], None] = "q8r9s0t1u2v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_proxies",
        sa.Column("is_dedicated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("ix_custom_proxies_is_dedicated", "custom_proxies", ["is_dedicated"])


def downgrade() -> None:
    op.drop_index("ix_custom_proxies_is_dedicated", table_name="custom_proxies")
    op.drop_column("custom_proxies", "is_dedicated")
