"""agent_sales_imported_contacts: Excel upload outreach for sales_manager

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-05-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sales_imported_contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("org_name", sa.String(length=512), nullable=False),
        sa.Column("lpr_name", sa.String(length=256), nullable=True),
        sa.Column("lpr_phone", sa.String(length=256), nullable=True),
        sa.Column("org_phone", sa.String(length=256), nullable=True),
        sa.Column("org_mobile", sa.String(length=256), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("whatsapp", sa.String(length=512), nullable=True),
        sa.Column("telegram", sa.String(length=512), nullable=True),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("target_external_id", sa.String(length=256), nullable=False),
        sa.Column("target_resolve_hint", sa.Text(), nullable=True),
        sa.Column("outreach_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "dedup_key", name="uq_agent_sales_imported_contact_dedup"),
    )
    op.create_index(
        op.f("ix_agent_sales_imported_contacts_agent_id"),
        "agent_sales_imported_contacts",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_sales_imported_contacts_import_batch_id"),
        "agent_sales_imported_contacts",
        ["import_batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_sales_imported_contacts_outreach_status"),
        "agent_sales_imported_contacts",
        ["outreach_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_sales_imported_contacts_created_at"),
        "agent_sales_imported_contacts",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_sales_imported_contacts_created_at"), table_name="agent_sales_imported_contacts")
    op.drop_index(op.f("ix_agent_sales_imported_contacts_outreach_status"), table_name="agent_sales_imported_contacts")
    op.drop_index(op.f("ix_agent_sales_imported_contacts_import_batch_id"), table_name="agent_sales_imported_contacts")
    op.drop_index(op.f("ix_agent_sales_imported_contacts_agent_id"), table_name="agent_sales_imported_contacts")
    op.drop_table("agent_sales_imported_contacts")
