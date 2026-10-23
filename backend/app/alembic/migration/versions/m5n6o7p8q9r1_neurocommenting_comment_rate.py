"""Comment every fresh post. The 30% dice was dropping most of the queue.

Pauses (join gap, action gap, post delay) stay as the task saved them.

Revision ID: m5n6o7p8q9r1
Revises: l4m5n6o7p9q0
Create Date: 2026-10-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m5n6o7p8q9r1"
down_revision: Union[str, Sequence[str], None] = "l4m5n6o7p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE custom_automations
            SET module_settings = jsonb_set(
                module_settings,
                '{neurocommenting,probability}',
                '100'::jsonb,
                false
            )
            WHERE jsonb_typeof(module_settings -> 'neurocommenting') = 'object'
              AND (module_settings #>> '{neurocommenting,probability}') ~ '^[0-9]+$'
              AND (module_settings #>> '{neurocommenting,probability}')::int < 100
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE custom_jobs
            SET params = jsonb_set(params, '{probability}', '100'::jsonb, false)
            WHERE job_type = 'neurocommenting'
              AND status IN ('pending', 'running', 'processing', 'awaiting_approval', 'paused')
              AND jsonb_typeof(params) = 'object'
              AND (params ->> 'probability') ~ '^[0-9]+$'
              AND (params ->> 'probability')::int < 100
            """
        )
    )


def downgrade() -> None:
    pass
