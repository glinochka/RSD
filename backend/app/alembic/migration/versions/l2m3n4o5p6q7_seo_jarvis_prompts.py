"""SEO-Джарвис prompt templates for seo_saas automations

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-09-03
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from prompt_data.seo_saas_prompts import PROMPT_MARKER, SEO_SAAS_PROMPTS


revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, Sequence[str], None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _apply_prompts(conn, automation_id: int, now: datetime) -> int:
    upgraded = 0
    for prompt_type, spec in SEO_SAAS_PROMPTS.items():
        row = conn.execute(
            sa.text(
                """
                SELECT id, version, content
                FROM custom_prompts
                WHERE custom_automation_id = :automation_id
                  AND prompt_type = :prompt_type
                  AND is_active = true
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"automation_id": automation_id, "prompt_type": prompt_type},
        ).fetchone()

        expected = spec["content"]
        if row:
            current = row[2] or ""
            if PROMPT_MARKER in current:
                continue
            if current.strip() == expected.strip():
                continue
            conn.execute(
                sa.text(
                    "UPDATE custom_prompts SET is_active = false, updated_at = :now WHERE id = :id"
                ),
                {"id": row[0], "now": now},
            )
            version = int(row[1]) + 1
        else:
            version = 1

        conn.execute(
            sa.text(
                """
                INSERT INTO custom_prompts (
                    custom_automation_id, prompt_type, name, content, model,
                    temperature, max_tokens, response_format, is_active, version,
                    created_at, updated_at
                ) VALUES (
                    :automation_id, :prompt_type, :name, :content, :model,
                    :temperature, :max_tokens, :response_format, true, :version,
                    :now, :now
                )
                """
            ),
            {
                "automation_id": automation_id,
                "prompt_type": prompt_type,
                "name": spec["name"],
                "content": expected,
                "model": spec.get("model", "deepseek-chat"),
                "temperature": spec.get("temperature", 0.7),
                "max_tokens": spec.get("max_tokens", 300),
                "response_format": spec.get("response_format", "json"),
                "version": version,
                "now": now,
            },
        )
        upgraded += 1
    return upgraded


def upgrade() -> None:
    conn = op.get_bind()
    now = _utcnow()
    automation_ids = [
        row[0]
        for row in conn.execute(
            sa.text("SELECT id FROM custom_automations WHERE solution_kind = 'seo_saas'")
        ).fetchall()
    ]
    for automation_id in automation_ids:
        _apply_prompts(conn, automation_id, now)


def downgrade() -> None:
    conn = op.get_bind()
    now = _utcnow()
    automation_ids = [
        row[0]
        for row in conn.execute(
            sa.text("SELECT id FROM custom_automations WHERE solution_kind = 'seo_saas'")
        ).fetchall()
    ]
    for automation_id in automation_ids:
        for prompt_type in SEO_SAAS_PROMPTS:
            row = conn.execute(
                sa.text(
                    """
                    SELECT id, content
                    FROM custom_prompts
                    WHERE custom_automation_id = :automation_id
                      AND prompt_type = :prompt_type
                      AND is_active = true
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"automation_id": automation_id, "prompt_type": prompt_type},
            ).fetchone()
            if not row or PROMPT_MARKER not in (row[1] or ""):
                continue
            conn.execute(
                sa.text(
                    "UPDATE custom_prompts SET is_active = false, updated_at = :now WHERE id = :id"
                ),
                {"id": row[0], "now": now},
            )
            prev = conn.execute(
                sa.text(
                    """
                    SELECT id FROM custom_prompts
                    WHERE custom_automation_id = :automation_id
                      AND prompt_type = :prompt_type
                      AND is_active = false
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"automation_id": automation_id, "prompt_type": prompt_type},
            ).fetchone()
            if prev:
                conn.execute(
                    sa.text(
                        "UPDATE custom_prompts SET is_active = true, updated_at = :now WHERE id = :id"
                    ),
                    {"id": prev[0], "now": now},
                )
