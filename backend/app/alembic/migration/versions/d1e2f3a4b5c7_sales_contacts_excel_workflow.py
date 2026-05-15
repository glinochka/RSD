"""sales_outbound_contacts: excel fields and workflow_status

Revision ID: d1e2f3a4b5c7
Revises: c7d8e9f0a1b2
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c7"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_sales_outbound_contacts_stage", "sales_outbound_contacts", type_="check")
    op.add_column(
        "sales_outbound_contacts",
        sa.Column("org_name", sa.String(length=512), nullable=False, server_default=""),
    )
    op.execute(
        sa.text("UPDATE sales_outbound_contacts SET org_name = COALESCE(NULLIF(TRIM(label), ''), '(без названия)')")
    )
    op.add_column("sales_outbound_contacts", sa.Column("lpr_name", sa.String(length=256), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("lpr_phone", sa.String(length=64), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("org_phone", sa.String(length=64), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("org_mobile", sa.String(length=64), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("import_status", sa.Text(), nullable=True))
    op.add_column(
        "sales_outbound_contacts",
        sa.Column("workflow_status", sa.String(length=32), nullable=False, server_default="new"),
    )
    op.execute(
        sa.text(
            """
            UPDATE sales_outbound_contacts SET workflow_status = CASE funnel_stage
                WHEN 'in_base' THEN 'new'
                WHEN 'called' THEN 'in_progress'
                WHEN 'demo' THEN 'demo'
                WHEN 'closed' THEN 'closed'
                ELSE 'new'
            END
            """
        )
    )
    op.add_column("sales_outbound_contacts", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("sales_outbound_contacts", sa.Column("website", sa.String(length=512), nullable=True))
    op.drop_column("sales_outbound_contacts", "funnel_stage")
    op.drop_column("sales_outbound_contacts", "label")
    op.create_index(
        op.f("ix_sales_outbound_contacts_workflow_status"),
        "sales_outbound_contacts",
        ["workflow_status"],
        unique=False,
    )
    op.drop_index("ix_sales_outbound_contacts_stage", table_name="sales_outbound_contacts")
    op.create_check_constraint(
        "ck_sales_outbound_contacts_workflow",
        "sales_outbound_contacts",
        "workflow_status IN ('new','in_progress','demo','closed','rejected','hesitating')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sales_outbound_contacts_workflow", "sales_outbound_contacts", type_="check")
    op.drop_index(op.f("ix_sales_outbound_contacts_workflow_status"), table_name="sales_outbound_contacts")
    op.add_column(
        "sales_outbound_contacts",
        sa.Column("label", sa.String(length=256), nullable=False, server_default=""),
    )
    op.add_column(
        "sales_outbound_contacts",
        sa.Column("funnel_stage", sa.String(length=16), nullable=False, server_default="in_base"),
    )
    op.execute(
        sa.text(
            """
            UPDATE sales_outbound_contacts SET label = LEFT(org_name, 256)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE sales_outbound_contacts SET funnel_stage = CASE workflow_status
                WHEN 'new' THEN 'in_base'
                WHEN 'in_progress' THEN 'called'
                WHEN 'demo' THEN 'demo'
                WHEN 'closed' THEN 'closed'
                WHEN 'rejected' THEN 'called'
                WHEN 'hesitating' THEN 'called'
                ELSE 'in_base'
            END
            """
        )
    )
    op.drop_column("sales_outbound_contacts", "website")
    op.drop_column("sales_outbound_contacts", "email")
    op.drop_column("sales_outbound_contacts", "comment")
    op.drop_column("sales_outbound_contacts", "import_status")
    op.drop_column("sales_outbound_contacts", "org_mobile")
    op.drop_column("sales_outbound_contacts", "org_phone")
    op.drop_column("sales_outbound_contacts", "lpr_phone")
    op.drop_column("sales_outbound_contacts", "lpr_name")
    op.drop_column("sales_outbound_contacts", "workflow_status")
    op.drop_column("sales_outbound_contacts", "org_name")
    op.create_index("ix_sales_outbound_contacts_stage", "sales_outbound_contacts", ["funnel_stage"], unique=False)
    op.create_check_constraint(
        "ck_sales_outbound_contacts_stage",
        "sales_outbound_contacts",
        "funnel_stage IN ('in_base','called','demo','closed')",
    )
