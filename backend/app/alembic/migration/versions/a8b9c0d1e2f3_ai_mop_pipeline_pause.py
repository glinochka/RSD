"""ai_mop_pipeline_state: global pause for generation and outreach

Revision ID: a8b9c0d1e2f3
Revises: z6a7b8c9d0e1
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "z6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_mop_pipeline_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("is_paused", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO ai_mop_pipeline_state (id, is_paused, updated_at) "
            "VALUES (1, false, CURRENT_TIMESTAMP)"
        )
    )


def downgrade() -> None:
    op.drop_table("ai_mop_pipeline_state")
