"""Make users.telegram_id nullable

Revision ID: b1e9b2f2c123
Revises: a4987f857d3f
Create Date: 2026-03-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1e9b2f2c123"
down_revision: Union[str, Sequence[str], None] = "a4987f857d3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow users without a telegram_id (web registration)."""
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    """Revert telegram_id back to NOT NULL."""
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

