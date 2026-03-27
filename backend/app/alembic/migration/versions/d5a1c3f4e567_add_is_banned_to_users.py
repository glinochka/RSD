"""add is_banned to users

Revision ID: d5a1c3f4e567
Revises: c3d8d2e2a921
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5a1c3f4e567"
down_revision: Union[str, Sequence[str], None] = "c3d8d2e2a921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("users", "is_banned")
