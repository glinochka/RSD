"""expand encrypted agent fields

Revision ID: a1f6c9d2e4b7
Revises: e9a1b7c3d5f6
Create Date: 2026-04-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f6c9d2e4b7"
down_revision: Union[str, Sequence[str], None] = "e9a1b7c3d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "agents",
        "encrypted_token",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "agents",
        "encrypted_external_api_key",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "agents",
        "encrypted_external_api_key",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "agents",
        "encrypted_token",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
