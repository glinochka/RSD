"""add encrypted booking payment api key to agents

Revision ID: l1m2n3o4p5q6r7
Revises: k0l1m2n3o4p5
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l1m2n3o4p5q6r7"
down_revision: Union[str, Sequence[str], None] = "k0l1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("encrypted_booking_payment_api_key", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "encrypted_booking_payment_api_key")
