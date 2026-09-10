"""chat folders from excel import; stop fake joined status

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, Sequence[str], None] = "m4n5o6p7q8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_automation_id", sa.Integer(), sa.ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_folders_custom_automation_id", "chat_folders", ["custom_automation_id"])
    op.create_unique_constraint("uq_chat_folder_automation_name", "chat_folders", ["custom_automation_id", "name"])
    op.add_column(
        "chat_targets",
        sa.Column("folder_id", sa.Integer(), sa.ForeignKey("chat_folders.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_chat_targets_folder_id", "chat_targets", ["folder_id"])
    op.execute(
        sa.text(
            """
            UPDATE chat_targets AS ct
            SET join_status = 'pending', updated_at = NOW()
            WHERE ct.join_status = 'joined'
              AND NOT EXISTS (
                SELECT 1 FROM account_chat_memberships m
                WHERE m.chat_target_id = ct.id AND m.join_status = 'joined'
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_chat_targets_folder_id", table_name="chat_targets")
    op.drop_column("chat_targets", "folder_id")
    op.drop_constraint("uq_chat_folder_automation_name", "chat_folders", type_="unique")
    op.drop_index("ix_chat_folders_custom_automation_id", table_name="chat_folders")
    op.drop_table("chat_folders")
