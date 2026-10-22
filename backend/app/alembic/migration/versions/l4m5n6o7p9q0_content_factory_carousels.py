"""Photo carousels for the content factory.

Revision ID: l4m5n6o7p9q0
Revises: k3l4m5n6o7p8
Create Date: 2026-10-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l4m5n6o7p9q0"
down_revision: Union[str, Sequence[str], None] = "k3l4m5n6o7p8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("carousel_share", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("image_provider", sa.String(length=32), nullable=False, server_default="chatgpt"),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("image_model", sa.String(length=128), nullable=False, server_default="gpt-image-2.5-flare"),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("xai_api_key_enc", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("custom_content_factory_settings", "xai_api_key_enc")
    op.drop_column("custom_content_factory_settings", "image_model")
    op.drop_column("custom_content_factory_settings", "image_provider")
    op.drop_column("custom_content_factory_settings", "carousel_share")
