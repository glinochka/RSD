"""Content factory: carousel-first default, music bed, VK clip fields.

Revision ID: n6o7p8q9r0s2
Revises: m5n6o7p8q9r1
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n6o7p8q9r0s2"
down_revision: Union[str, Sequence[str], None] = "m5n6o7p8q9r1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("music_mode", sa.String(length=16), nullable=False, server_default="voice_bed"),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("music_volume", sa.Integer(), nullable=False, server_default="32"),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("tts_voice", sa.String(length=64), nullable=False, server_default=""),
    )
    op.alter_column(
        "custom_content_factory_settings",
        "carousel_share",
        server_default="100",
    )
    op.execute(
        sa.text(
            "UPDATE custom_content_factory_settings SET carousel_share = 100 WHERE carousel_share = 0"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE custom_content_factory_settings SET carousel_share = 0 WHERE carousel_share = 100"
        )
    )
    op.alter_column(
        "custom_content_factory_settings",
        "carousel_share",
        server_default="0",
    )
    op.drop_column("custom_content_factory_settings", "tts_voice")
    op.drop_column("custom_content_factory_settings", "music_volume")
    op.drop_column("custom_content_factory_settings", "music_mode")
