"""sales_outbound_contacts: widen phone columns for multi-number imports

Revision ID: f9a0b1c2d3e4
Revises: e8f0a1b2c3d4
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e8f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in ("lpr_phone", "org_phone", "org_mobile"):
        op.alter_column(
            "sales_outbound_contacts",
            col,
            existing_type=sa.String(length=64),
            type_=sa.String(length=256),
            existing_nullable=True,
        )


def downgrade() -> None:
    for col in ("lpr_phone", "org_phone", "org_mobile"):
        op.alter_column(
            "sales_outbound_contacts",
            col,
            existing_type=sa.String(length=256),
            type_=sa.String(length=64),
            existing_nullable=True,
        )
