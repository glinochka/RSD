"""Exclusive proxy set per pool account.

Revision ID: p8q9r0s1t2u4
Revises: o7p8q9r0s1t3
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p8q9r0s1t2u4"
down_revision: Union[str, Sequence[str], None] = "o7p8q9r0s1t3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pool_accounts",
        sa.Column(
            "proxy_set_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "pool_accounts",
        sa.Column(
            "proxy_problem",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("pool_accounts", "proxy_problem")
    op.drop_column("pool_accounts", "proxy_set_ids")
