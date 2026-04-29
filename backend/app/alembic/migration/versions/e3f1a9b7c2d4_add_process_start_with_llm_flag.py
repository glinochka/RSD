"""add process_start_with_llm to agents

Revision ID: e3f1a9b7c2d4
Revises: b74f2d1a9c31
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f1a9b7c2d4"
down_revision: Union[str, Sequence[str], None] = "b74f2d1a9c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "process_start_with_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "process_start_with_llm")
