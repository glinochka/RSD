"""One saved Grok carousel bot per content factory.

Revision ID: o7p8q9r0s1t3
Revises: n6o7p8q9r0s2
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o7p8q9r0s1t3"
down_revision: Union[str, Sequence[str], None] = "n6o7p8q9r0s2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("grok_bot_name", sa.String(length=80), nullable=False, server_default="Карусели завода"),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("grok_bot_brief", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "custom_content_factory_settings",
        sa.Column("grok_bot_response_id", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("custom_content_factory_settings", "grok_bot_response_id")
    op.drop_column("custom_content_factory_settings", "grok_bot_brief")
    op.drop_column("custom_content_factory_settings", "grok_bot_name")
