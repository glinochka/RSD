"""Create Date: 2026-10-05 parser_users for the UBT parser module.

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, Sequence[str], None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parser_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column("source_mode", sa.String(32), nullable=False, server_default="messages"),
        sa.Column("source_chat_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("source_title", sa.String(255), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_photo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_parser_users_automation_id", "parser_users", ["custom_automation_id"])
    op.create_index("ix_parser_users_telegram_user_id", "parser_users", ["telegram_user_id"])
    op.create_index("ix_parser_users_created_at", "parser_users", ["created_at"])
    op.create_unique_constraint("uq_parser_user_chat", "parser_users", ["custom_automation_id", "telegram_user_id", "source_chat_id"])


def downgrade() -> None:
    op.drop_constraint("uq_parser_user_chat", "parser_users", type_="unique")
    op.drop_index("ix_parser_users_created_at", table_name="parser_users")
    op.drop_index("ix_parser_users_telegram_user_id", table_name="parser_users")
    op.drop_index("ix_parser_users_automation_id", table_name="parser_users")
    op.drop_table("parser_users")
