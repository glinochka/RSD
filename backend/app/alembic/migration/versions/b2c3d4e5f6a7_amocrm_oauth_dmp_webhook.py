"""amocrm oauth credentials and dmp webhook secret

Revision ID: b2c3d4e5f6a7
Revises: a9b0c1d2e3f4
Create Date: 2026-08-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column("dmp_webhook_secret", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "amocrm_connections",
        sa.Column("client_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "amocrm_connections",
        sa.Column("client_secret_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "amocrm_connections",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.alter_column(
        "amocrm_connections",
        "access_token_hash",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        nullable=True,
    )
    op.alter_column(
        "amocrm_connections",
        "refresh_token_hash",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "amocrm_connections",
        "refresh_token_hash",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "amocrm_connections",
        "access_token_hash",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        nullable=False,
    )
    op.drop_column("amocrm_connections", "expires_at")
    op.drop_column("amocrm_connections", "client_secret_enc")
    op.drop_column("amocrm_connections", "client_id")
    op.drop_column("custom_automations", "dmp_webhook_secret")
