"""add external webhook url to agents

Revision ID: a4b6c8d1e2f3
Revises: f4c9a1e2b6d8
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4b6c8d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f4c9a1e2b6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("external_webhook_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "external_webhook_url")
