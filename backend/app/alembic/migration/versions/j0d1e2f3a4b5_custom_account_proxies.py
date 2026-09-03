"""custom account proxies and even assignment

Revision ID: j0d1e2f3a4b5
Revises: i9c0d1e2f3a4
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "j0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "i9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_automations", sa.Column("proxy_list_text", sa.Text(), nullable=True))
    op.add_column(
        "social_accounts",
        sa.Column("telegram_proxy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "custom_proxies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("scheme", sa.String(length=16), server_default="socks5", nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("password_enc", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custom_automation_id", "fingerprint", name="uq_custom_proxy_fingerprint"),
    )
    op.create_index("ix_custom_proxies_custom_automation_id", "custom_proxies", ["custom_automation_id"])
    op.create_index("ix_custom_proxies_fingerprint", "custom_proxies", ["fingerprint"])
    op.create_index("ix_custom_proxies_is_active", "custom_proxies", ["is_active"])
    op.add_column("pool_accounts", sa.Column("proxy_id", sa.Integer(), nullable=True))
    op.create_index("ix_pool_accounts_proxy_id", "pool_accounts", ["proxy_id"])
    op.create_foreign_key(
        "fk_pool_accounts_proxy_id",
        "pool_accounts",
        "custom_proxies",
        ["proxy_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_pool_accounts_proxy_id", "pool_accounts", type_="foreignkey")
    op.drop_index("ix_pool_accounts_proxy_id", table_name="pool_accounts")
    op.drop_column("pool_accounts", "proxy_id")
    op.drop_index("ix_custom_proxies_is_active", table_name="custom_proxies")
    op.drop_index("ix_custom_proxies_fingerprint", table_name="custom_proxies")
    op.drop_index("ix_custom_proxies_custom_automation_id", table_name="custom_proxies")
    op.drop_table("custom_proxies")
    op.drop_column("social_accounts", "telegram_proxy")
    op.drop_column("custom_automations", "proxy_list_text")
