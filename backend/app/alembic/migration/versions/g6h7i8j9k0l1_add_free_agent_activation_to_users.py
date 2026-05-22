"""add free_agent_activation to users

Revision ID: g6h7i8j9k0l1
Revises: f5e6a7b8c9d0
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6h7i8j9k0l1"
down_revision: Union[str, Sequence[str], None] = "f5e6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "free_agent_activation",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "free_agent_activation")
