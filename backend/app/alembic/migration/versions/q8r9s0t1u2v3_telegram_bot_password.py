"""telegram bot password for lead handoff

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q8r9s0t1u2v3"
down_revision: Union[str, Sequence[str], None] = "p7q8r9s0t1u2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_automations", sa.Column("telegram_bot_password_hash", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("custom_automations", "telegram_bot_password_hash")
