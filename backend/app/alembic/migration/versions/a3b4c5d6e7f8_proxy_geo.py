"""Store proxy country, region and IP version for geo assignment.

Revision ID: a3b4c5d6e7f8
Revises: z1a2b3c4d5e6
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_proxies", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column("custom_proxies", sa.Column("region", sa.String(length=16), nullable=True))
    op.add_column("custom_proxies", sa.Column("ip_version", sa.Integer(), nullable=True))
    op.create_index("ix_custom_proxies_country_code", "custom_proxies", ["country_code"])
    op.create_index("ix_custom_proxies_region", "custom_proxies", ["region"])


def downgrade() -> None:
    op.drop_index("ix_custom_proxies_region", table_name="custom_proxies")
    op.drop_index("ix_custom_proxies_country_code", table_name="custom_proxies")
    op.drop_column("custom_proxies", "ip_version")
    op.drop_column("custom_proxies", "region")
    op.drop_column("custom_proxies", "country_code")
