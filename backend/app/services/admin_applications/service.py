"""CRUD service for admin application intake."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AdminApplication
from .fields import APPLICATION_STATUSES, normalize_application_fields, validate_field_values

_service_singleton: "AdminApplicationService | None" = None


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize_row(row: AdminApplication) -> dict[str, Any]:
    try:
        fields_data = json.loads(row.fields_json or "{}")
    except (TypeError, json.JSONDecodeError):
        fields_data = {}
    if not isinstance(fields_data, dict):
        fields_data = {}
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "client_external_id": row.client_external_id,
        "client_name": row.client_name,
        "status": row.status,
        "fields": fields_data,
        "source_channel": row.source_channel,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class AdminApplicationService:
    def get_fields_schema(self, template_config: dict[str, Any] | None) -> list[dict[str, Any]]:
        cfg = template_config if isinstance(template_config, dict) else {}
        try:
            return normalize_application_fields(cfg.get("application_fields"))
        except ValueError:
            return []

    async def create_application(
        self,
        session: AsyncSession,
        *,
        agent_id: int,
        template_config: dict[str, Any] | None,
        client_external_id: str,
        client_name: str | None,
        fields: dict[str, Any] | None,
        source_channel: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        schema = self.get_fields_schema(template_config)
        if not schema:
            raise ValueError("Схема полей заявки не настроена для этого агента")
        validated = validate_field_values(schema, fields)
        if not validated:
            raise ValueError("Заполните хотя бы одно поле заявки")
        now = _utc_now_naive()
        row = AdminApplication(
            agent_id=agent_id,
            client_external_id=(client_external_id or "anonymous").strip() or "anonymous",
            client_name=(client_name or "").strip() or None,
            status="new",
            fields_json=json.dumps(validated, ensure_ascii=False),
            source_channel=(source_channel or "").strip().lower() or None,
            notes=(notes or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return _serialize_row(row)

    async def list_applications(
        self,
        session: AsyncSession,
        *,
        agent_id: int,
        status: str | None = None,
        client_external_id: str | None = None,
        source_channel: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = [AdminApplication.agent_id == agent_id]
        if status:
            normalized = str(status).strip().lower()
            if normalized in APPLICATION_STATUSES:
                conditions.append(AdminApplication.status == normalized)
        if client_external_id:
            conditions.append(AdminApplication.client_external_id == str(client_external_id).strip())
        if source_channel:
            conditions.append(AdminApplication.source_channel == str(source_channel).strip().lower())
        stmt = (
            select(AdminApplication)
            .where(and_(*conditions))
            .order_by(desc(AdminApplication.created_at))
            .limit(max(1, min(int(limit), 500)))
            .offset(max(0, int(offset)))
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [_serialize_row(row) for row in rows]

    async def get_application(
        self,
        session: AsyncSession,
        *,
        agent_id: int,
        application_id: int,
    ) -> dict[str, Any] | None:
        row = await session.get(AdminApplication, application_id)
        if row is None or row.agent_id != agent_id:
            return None
        return _serialize_row(row)

    async def update_application(
        self,
        session: AsyncSession,
        *,
        agent_id: int,
        application_id: int,
        status: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        row = await session.get(AdminApplication, application_id)
        if row is None or row.agent_id != agent_id:
            return None
        if status is not None:
            normalized = str(status).strip().lower()
            if normalized not in APPLICATION_STATUSES:
                raise ValueError(f"status must be one of: {', '.join(sorted(APPLICATION_STATUSES))}")
            row.status = normalized
        if notes is not None:
            row.notes = str(notes).strip() or None
        row.updated_at = _utc_now_naive()
        await session.flush()
        await session.refresh(row)
        return _serialize_row(row)

    async def count_by_status(
        self,
        session: AsyncSession,
        *,
        agent_id: int,
        source_channel: str | None = None,
    ) -> dict[str, int]:
        conditions = [AdminApplication.agent_id == agent_id]
        if source_channel:
            conditions.append(AdminApplication.source_channel == str(source_channel).strip().lower())
        rows = (
            await session.execute(
                select(AdminApplication.status, AdminApplication.id).where(and_(*conditions))
            )
        ).all()
        counts = {status: 0 for status in APPLICATION_STATUSES}
        for status, _ in rows:
            key = str(status or "").strip().lower()
            if key in counts:
                counts[key] += 1
        counts["total"] = len(rows)
        return counts


def get_admin_application_service() -> AdminApplicationService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = AdminApplicationService()
    return _service_singleton
