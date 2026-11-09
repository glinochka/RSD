"""One proxy address per content-factory account.

Revision ID: q9r0s1t2u3v5
Revises: p8q9r0s1t2u4
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q9r0s1t2u3v5"
down_revision: Union[str, Sequence[str], None] = "p8q9r0s1t2u4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custom_content_factory_accounts",
        sa.Column("proxy_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "custom_content_factory_accounts",
        sa.Column("proxy_problem", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(
        "ix_cf_accounts_proxy_id",
        "custom_content_factory_accounts",
        ["proxy_id"],
    )
    op.create_foreign_key(
        "fk_cf_accounts_proxy_id",
        "custom_content_factory_accounts",
        "custom_proxies",
        ["proxy_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cf_accounts_proxy_id", "custom_content_factory_accounts", type_="foreignkey")
    op.drop_index("ix_cf_accounts_proxy_id", table_name="custom_content_factory_accounts")
    op.drop_column("custom_content_factory_accounts", "proxy_problem")
    op.drop_column("custom_content_factory_accounts", "proxy_id")
