"""merge alembic heads: user_error_reports + crm tool analytics fields

Revision ID: f7a3c9e2b8d1
Revises: d0e1f2a3b4c5, e2b4a9c7d1f3
Create Date: 2026-04-23
"""

from typing import Sequence, Union


revision: str = "f7a3c9e2b8d1"
down_revision: Union[str, Sequence[str], None] = ("d0e1f2a3b4c5", "e2b4a9c7d1f3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
