"""Account humanization rest: separate next_humanization_at from target action rest.

Target actions (neurocommenting, shilling, dm) now rest 40-70 min via next_action_at.
Humanization actions (warmup DMs, idle browse, reactions) rest 15-30 min via next_humanization_at.
The two timers are independent so warmup/browsing never blocks target action slots.

Revision ID: a0b1c2d3e4f5
Revises: s0t1u2v3w4x5
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "s0t1u2v3w4x5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column("next_humanization_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_social_accounts_next_humanization_at",
        "social_accounts",
        ["next_humanization_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_social_accounts_next_humanization_at", table_name="social_accounts")
    op.drop_column("social_accounts", "next_humanization_at")
