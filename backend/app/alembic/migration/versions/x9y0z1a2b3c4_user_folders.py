"""Create Date: 2026-10-06 user folders from parser jobs.

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x9y0z1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "w8x9y0z1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="parser"),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("custom_automation_id", "name", name="uq_user_folder_automation_name"),
    )
    op.create_index("ix_user_folders_automation_id", "user_folders", ["custom_automation_id"])
    op.create_table(
        "user_folder_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_folder_id", sa.Integer(), sa.ForeignKey("user_folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column("source_title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_folder_id", "telegram_user_id", name="uq_user_folder_member"),
    )
    op.create_index("ix_user_folder_members_folder_id", "user_folder_members", ["user_folder_id"])
    op.create_index("ix_user_folder_members_automation_id", "user_folder_members", ["custom_automation_id"])


def downgrade() -> None:
    op.drop_index("ix_user_folder_members_automation_id", table_name="user_folder_members")
    op.drop_index("ix_user_folder_members_folder_id", table_name="user_folder_members")
    op.drop_table("user_folder_members")
    op.drop_index("ix_user_folders_automation_id", table_name="user_folders")
    op.drop_table("user_folders")
