"""seed seo saas and fulfillment automations

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-25
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    op.add_column(
        "custom_automations",
        sa.Column("solution_kind", sa.String(length=32), server_default="generic", nullable=False),
    )
    op.add_column(
        "custom_automations",
        sa.Column("solution_slug", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("partner_utm_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("partner_promo_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "custom_automations",
        sa.Column("conversion_check_url", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_custom_automations_solution_kind", "custom_automations", ["solution_kind"])
    op.create_index("ix_custom_automations_solution_slug", "custom_automations", ["solution_slug"], unique=True)

    conn = op.get_bind()
    now = _utcnow()
    existing_slugs = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT solution_slug FROM custom_automations WHERE solution_slug IS NOT NULL")
        ).fetchall()
    }

    solutions = [
        {
            "name": "SEO SaaS",
            "client_name": "SEO SaaS",
            "industry": "seo_saas",
            "description": "Партизанский маркетинг и DMP для SaaS SEO-продвижения. Без отдела продаж: доверенный аккаунт закрывает регистрацию по UTM/промокоду.",
            "status": "active",
            "is_chat_monitoring_enabled": True,
            "is_neurocommenting_enabled": True,
            "is_digital_footprint_enabled": True,
            "is_dmp_one_enabled": True,
            "is_amocrm_enabled": False,
            "is_shilling_enabled": True,
            "solution_kind": "seo_saas",
            "solution_slug": "seo-saas",
        },
        {
            "name": "Фулфилмент",
            "client_name": "Фулфилмент",
            "industry": "fulfillment",
            "description": "Партизанский маркетинг, DMP и прогрев доверенным аккаунтом с передачей в отдел продаж и AmoCRM.",
            "status": "active",
            "is_chat_monitoring_enabled": True,
            "is_neurocommenting_enabled": True,
            "is_digital_footprint_enabled": True,
            "is_dmp_one_enabled": True,
            "is_amocrm_enabled": True,
            "is_shilling_enabled": True,
            "solution_kind": "fulfillment",
            "solution_slug": "fulfillment",
        },
    ]

    insert_automation = sa.text(
        """
        INSERT INTO custom_automations (
            name, client_name, industry, description, status,
            is_chat_monitoring_enabled, is_neurocommenting_enabled, is_digital_footprint_enabled,
            is_dmp_one_enabled, is_amocrm_enabled, is_shilling_enabled,
            solution_kind, solution_slug, rotation_strategy, max_daily_messages_per_account,
            lead_warmup_enabled, created_at, updated_at
        ) VALUES (
            :name, :client_name, :industry, :description, :status,
            :is_chat_monitoring_enabled, :is_neurocommenting_enabled, :is_digital_footprint_enabled,
            :is_dmp_one_enabled, :is_amocrm_enabled, :is_shilling_enabled,
            :solution_kind, :solution_slug, 'round_robin', 50,
            true, :created_at, :updated_at
        )
        """
    )
    insert_pool = sa.text(
        """
        INSERT INTO account_pools (
            custom_automation_id, name, description, is_default, created_at, updated_at
        ) VALUES (
            :custom_automation_id, 'Default', 'Default pool created automatically', true, :created_at, :updated_at
        )
        """
    )

    for spec in solutions:
        if spec["solution_slug"] in existing_slugs:
            continue
        params = {**spec, "created_at": now, "updated_at": now}
        conn.execute(insert_automation, params)
        automation_id = conn.execute(
            sa.text("SELECT id FROM custom_automations WHERE solution_slug = :slug"),
            {"slug": spec["solution_slug"]},
        ).scalar()
        if automation_id:
            conn.execute(
                insert_pool,
                {
                    "custom_automation_id": automation_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM custom_automations WHERE solution_slug IN ('seo-saas', 'fulfillment')")
    )
    op.drop_index("ix_custom_automations_solution_slug", table_name="custom_automations")
    op.drop_index("ix_custom_automations_solution_kind", table_name="custom_automations")
    op.drop_column("custom_automations", "conversion_check_url")
    op.drop_column("custom_automations", "partner_promo_code")
    op.drop_column("custom_automations", "partner_utm_url")
    op.drop_column("custom_automations", "solution_slug")
    op.drop_column("custom_automations", "solution_kind")
