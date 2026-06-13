"""sales_outbound_contacts: whatsapp, telegram, messenger_max

Revision ID: a1b2c3d4e5f7
Revises: f9a0b1c2d3e4
Create Date: 2026-05-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales_outbound_contacts", sa.Column("whatsapp", sa.String(length=512), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("telegram", sa.String(length=512), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("messenger_max", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_outbound_contacts", "messenger_max")
    op.drop_column("sales_outbound_contacts", "telegram")
    op.drop_column("sales_outbound_contacts", "whatsapp")
