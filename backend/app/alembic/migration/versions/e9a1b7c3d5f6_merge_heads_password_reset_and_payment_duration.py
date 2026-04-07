"""merge heads: password reset and payment duration

Revision ID: e9a1b7c3d5f6
Revises: d8f1a2c3b4e5, b2d7f4c1a9e6
Create Date: 2026-04-07
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "e9a1b7c3d5f6"
down_revision: Union[str, Sequence[str], None] = ("d8f1a2c3b4e5", "b2d7f4c1a9e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration: no schema changes, only reconciles Alembic heads.
    pass


def downgrade() -> None:
    # Split merged head back into two branches.
    pass
