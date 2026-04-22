"""merge heads: sales dm queue and sales contacts

Revision ID: f4c9a1e2b6d8
Revises: c5d2e9f3a1b4, a9f1d2e3c4b5
Create Date: 2026-04-23
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f4c9a1e2b6d8"
down_revision: Union[str, Sequence[str], None] = ("c5d2e9f3a1b4", "a9f1d2e3c4b5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration: no schema changes, only reconciles Alembic heads.
    pass


def downgrade() -> None:
    # Split merged head back into two branches.
    pass
