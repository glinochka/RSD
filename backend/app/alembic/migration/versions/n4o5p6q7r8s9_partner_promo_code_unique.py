"""partner promo codes globally unique by code

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op


revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, Sequence[str], None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_partner_promo_codes_partner_code",
        "partner_promo_codes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_partner_promo_codes_code",
        "partner_promo_codes",
        ["code"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_partner_promo_codes_code", "partner_promo_codes", type_="unique")
    op.create_unique_constraint(
        "uq_partner_promo_codes_partner_code",
        "partner_promo_codes",
        ["partner_user_id", "code"],
    )
