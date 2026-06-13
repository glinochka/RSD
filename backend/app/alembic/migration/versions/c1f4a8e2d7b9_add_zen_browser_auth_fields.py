"""Add Zen browser auth fields (login/password) for article publisher

Revision ID: c1f4a8e2d7b9
Revises: b9e4f2a7c1d3
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1f4a8e2d7b9"
down_revision: Union[str, Sequence[str], None] = "b9e4f2a7c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "article_publisher_settings",
        sa.Column("zen_login", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "article_publisher_settings",
        sa.Column("zen_password_enc", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("article_publisher_settings", "zen_password_enc")
    op.drop_column("article_publisher_settings", "zen_login")
