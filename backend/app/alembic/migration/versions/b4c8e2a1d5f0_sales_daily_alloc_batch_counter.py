"""sales_team_members: track daily pool allocation for half-batch workflow

Revision ID: b4c8e2a1d5f0
Revises: a1b2c3d4e5f6
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c8e2a1d5f0"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_team_members",
        sa.Column(
            "daily_pool_alloc_total",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("sales_team_members", "daily_pool_alloc_total")
