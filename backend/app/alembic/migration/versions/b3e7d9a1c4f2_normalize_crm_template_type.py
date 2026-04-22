"""normalize crm template type and config defaults

Revision ID: b3e7d9a1c4f2
Revises: a1f6c9d2e4b7
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3e7d9a1c4f2"
down_revision: Union[str, Sequence[str], None] = "a1f6c9d2e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE agents
            SET template_type = 'crm_admin'
            WHERE template_type = 'function_calling'
            """
        )
    )
    default_crm_config = (
        '{"crm_provider":"amocrm","allowed_tools":["find_contact","create_contact","find_lead","create_lead","update_lead","add_note","create_task","assign_owner"],'
        '"confirmation_policy":"confirm_risky","fallback_mode":"ask_clarifying_question","field_mapping":null}'
    )
    op.execute(
        sa.text(
            """
            UPDATE agents
            SET template_config = :default_crm_config
            WHERE template_type = 'crm_admin' AND (template_config IS NULL OR btrim(template_config) = '')
            """
        ).bindparams(default_crm_config=default_crm_config)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE agents
            SET template_type = 'function_calling'
            WHERE template_type = 'crm_admin'
            """
        )
    )
