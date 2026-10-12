"""Store intercept cloud password and reauth start time.

Revision ID: h0b1c2d3e4f5
Revises: g9a0b1c2d3e4
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "g9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_accounts", sa.Column("encrypted_cloud_password", sa.Text(), nullable=True))
    op.add_column("social_accounts", sa.Column("intercept_reauth_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("social_accounts", "intercept_reauth_started_at")
    op.drop_column("social_accounts", "encrypted_cloud_password")
