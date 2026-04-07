"""add duration_months to website payment transactions

Revision ID: b2d7f4c1a9e6
Revises: d4f1a8b9c2e3
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2d7f4c1a9e6"
down_revision: Union[str, Sequence[str], None] = "d4f1a8b9c2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "website_payment_transactions",
        sa.Column("duration_months", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("website_payment_transactions", "duration_months", server_default=None)


def downgrade() -> None:
    op.drop_column("website_payment_transactions", "duration_months")
