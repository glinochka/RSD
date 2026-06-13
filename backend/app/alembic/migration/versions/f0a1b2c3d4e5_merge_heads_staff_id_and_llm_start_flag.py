"""merge heads for staff id and process_start_with_llm

Revision ID: f0a1b2c3d4e5
Revises: c2e5a7b8d9f1, e3f1a9b7c2d4
Create Date: 2026-04-29
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = ("c2e5a7b8d9f1", "e3f1a9b7c2d4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
