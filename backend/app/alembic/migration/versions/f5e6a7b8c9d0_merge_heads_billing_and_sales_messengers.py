"""merge heads: agent billing/telephony and sales contact messengers

Revision ID: f5e6a7b8c9d0
Revises: f4a5b6c7d8e9, a1b2c3d4e5f7
Create Date: 2026-05-20
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f5e6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = ("f4a5b6c7d8e9", "a1b2c3d4e5f7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration: no schema changes, only reconciles Alembic heads.
    pass


def downgrade() -> None:
    # Split merged head back into two branches.
    pass
