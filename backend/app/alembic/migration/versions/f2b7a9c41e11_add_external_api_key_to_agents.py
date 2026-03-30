"""add external api key to agents

Revision ID: f2b7a9c41e11
Revises: e1a4f83d9f12
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2b7a9c41e11"
down_revision: Union[str, Sequence[str], None] = "e1a4f83d9f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("encrypted_external_api_key", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("external_api_key_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_agents_external_api_key_hash", "agents", ["external_api_key_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_agents_external_api_key_hash", "agents", type_="unique")
    op.drop_column("agents", "external_api_key_hash")
    op.drop_column("agents", "encrypted_external_api_key")
