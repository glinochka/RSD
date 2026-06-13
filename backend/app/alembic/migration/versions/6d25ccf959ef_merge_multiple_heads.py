"""merge multiple heads

Revision ID: 6d25ccf959ef
Revises: c1f4a8e2d7b9, d2f6a1b3c9e8
Create Date: 2026-05-06 19:49:29.181211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d25ccf959ef'
down_revision: Union[str, Sequence[str], None] = ('c1f4a8e2d7b9', 'd2f6a1b3c9e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
