"""Bitrix24 CRM provider implementation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .base import CRMConnectionHealth, CRMProvider

_ENTITY_METHOD_PREFIX = {
    "lead": "crm.lead",
    "contact": "crm.contact",
    "company": "crm.company",
}

_TASK_BIND_PREFIX = {
    "lead": "L",
    "contact": "C",
    "company": "CO",
}


class Bitrix24Provider(CRMProvider):
    provider_name = "bitrix24"

    def __init__(self, *, base_url: str, access_token: str, timeout_seconds: float = 20.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token.strip()
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))

    async def _request(self, method_name: str, *, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}/{method_name}.json"
        params = {"auth": self._access_token}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, params=params, json=payload or {})
        if not response.is_success:
            detail = response.text[:500]
            raise RuntimeError(f"Bitrix24 request failed: HTTP {response.status_code} {detail}")
        data = response.json() if response.content else {}
        if isinstance(data, dict) and data.get("error"):
            description = str(data.get("error_description") or data.get("error"))
            raise RuntimeError(f"Bitrix24 API error: {description}")
        return data.get("result", data)

    @staticmethod
    def _entity_method_prefix(entity_type: str) -> str:
        normalized = (entity_type or "").strip().lower()
        method_prefix = _ENTITY_METHOD_PREFIX.get(normalized)
        if not method_prefix:
            raise RuntimeError("Unsupported entity_type")
        return method_prefix

    @staticmethod
    def _task_bind_code(entity_type: str, entity_id: int) -> str:
        normalized = (entity_type or "").strip().lower()
        prefix = _TASK_BIND_PREFIX.get(normalized)
        if not prefix:
            raise RuntimeError("Unsupported entity_type")
        return f"{prefix}_{int(entity_id)}"

    async def validate_connection(self) -> CRMConnectionHealth:
        profile = await self._request("user.current")
        user_id = str(profile.get("ID") or "")
        return CRMConnectionHealth(
            ok=bool(user_id),
            provider=self.provider_name,
            external_id=user_id or self._base_url,
            details={
                "name": profile.get("NAME"),
                "last_name": profile.get("LAST_NAME"),
                "email": profile.get("EMAIL"),
            },
        )

    async def find_contact(self, *, query: str) -> dict[str, Any]:
        items = await self._request(
            "crm.contact.list",
            payload={
                "filter": {"FIND": query},
                "select": ["ID", "NAME", "PHONE", "EMAIL"],
            },
        )
        return {"items": items}

    async def create_contact(self, *, name: str, phone: str | None = None, email: str | None = None) -> dict[str, Any]:
        fields: dict[str, Any] = {"NAME": name}
        if phone:
            fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"}]
        if email:
            fields["EMAIL"] = [{"VALUE": email, "VALUE_TYPE": "WORK"}]
        result = await self._request("crm.contact.add", payload={"fields": fields})
        return {"id": result}

    async def find_lead(self, *, query: str) -> dict[str, Any]:
        items = await self._request(
            "crm.lead.list",
            payload={
                "filter": {"FIND": query},
                "select": ["ID", "TITLE", "STATUS_ID", "OPPORTUNITY"],
            },
        )
        return {"items": items}

    async def create_lead(self, *, name: str, price: int | None = None) -> dict[str, Any]:
        fields: dict[str, Any] = {"TITLE": name}
        if price is not None:
            fields["OPPORTUNITY"] = int(price)
        result = await self._request("crm.lead.add", payload={"fields": fields})
        return {"id": result}

    async def update_lead(self, *, lead_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        mapped_fields = dict(fields)
        if "name" in mapped_fields and "TITLE" not in mapped_fields:
            mapped_fields["TITLE"] = mapped_fields.pop("name")
        if "price" in mapped_fields and "OPPORTUNITY" not in mapped_fields:
            mapped_fields["OPPORTUNITY"] = mapped_fields.pop("price")
        result = await self._request(
            "crm.lead.update",
            payload={
                "id": int(lead_id),
                "fields": mapped_fields,
            },
        )
        return {"updated": bool(result)}

    async def add_note(self, *, entity_type: str, entity_id: int, text: str) -> dict[str, Any]:
        entity_kind = (entity_type or "").strip().lower()
        self._entity_method_prefix(entity_kind)
        result = await self._request(
            "crm.timeline.comment.add",
            payload={
                "fields": {
                    "ENTITY_ID": int(entity_id),
                    "ENTITY_TYPE": entity_kind,
                    "COMMENT": text,
                }
            },
        )
        return {"id": result}

    async def create_task(
        self,
        *,
        text: str,
        complete_till_unix: int,
        entity_type: str,
        entity_id: int,
        responsible_user_id: int | None = None,
    ) -> dict[str, Any]:
        deadline = datetime.fromtimestamp(int(complete_till_unix), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fields: dict[str, Any] = {
            "TITLE": text[:120],
            "DESCRIPTION": text,
            "DEADLINE": deadline,
            "UF_CRM_TASK": [self._task_bind_code(entity_type, int(entity_id))],
        }
        if responsible_user_id is not None:
            fields["RESPONSIBLE_ID"] = int(responsible_user_id)
        result = await self._request("tasks.task.add", payload={"fields": fields})
        if isinstance(result, dict):
            task = result.get("task") or {}
            return {"id": task.get("id")}
        return {"id": result}

    async def assign_owner(self, *, entity_type: str, entity_id: int, responsible_user_id: int) -> dict[str, Any]:
        method_prefix = self._entity_method_prefix(entity_type)
        result = await self._request(
            f"{method_prefix}.update",
            payload={
                "id": int(entity_id),
                "fields": {"ASSIGNED_BY_ID": int(responsible_user_id)},
            },
        )
        return {"updated": bool(result)}
