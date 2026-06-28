"""ai_mop_leads: LLM token usage and cost tracking

Revision ID: c1d2e3f4a5b6
Revises: a8b9c0d1e2f3
Create Date: 2026-06-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_mop_leads",
        sa.Column("llm_prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_mop_leads",
        sa.Column("llm_completion_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_mop_leads",
        sa.Column("llm_cost_cny_micros", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("ai_mop_leads", "llm_cost_cny_micros")
    op.drop_column("ai_mop_leads", "llm_completion_tokens")
    op.drop_column("ai_mop_leads", "llm_prompt_tokens")
