"""amoCRM provider implementation."""
from __future__ import annotations

from typing import Any

import httpx

from .base import CRMConnectionHealth, CRMProvider


class AmoCRMProvider(CRMProvider):
    provider_name = "amocrm"

    def __init__(self, *, base_url: str, access_token: str, timeout_seconds: float = 20.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token.strip()
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, *, json_body: Any = None, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(method, url, headers=self._headers(), json=json_body, params=params)
        if not response.is_success:
            detail = response.text[:500]
            raise RuntimeError(f"amoCRM request failed: HTTP {response.status_code} {detail}")
        if not response.content:
            return {}
        return response.json()

    async def validate_connection(self) -> CRMConnectionHealth:
        account = await self._request("GET", "/api/v4/account")
        account_id = str(account.get("id") or "")
        return CRMConnectionHealth(
            ok=bool(account_id),
            provider=self.provider_name,
            external_id=account_id or self._base_url,
            details={
                "name": account.get("name"),
                "amojo_id": account.get("amojo_id"),
                "timezone": account.get("timezone"),
            },
        )

    async def find_contact(self, *, query: str) -> dict[str, Any]:
        return await self._request("GET", "/api/v4/contacts", params={"query": query})

    async def create_contact(self, *, name: str, phone: str | None = None, email: str | None = None) -> dict[str, Any]:
        custom_fields_values = []
        if phone:
            custom_fields_values.append({"field_code": "PHONE", "values": [{"value": phone}]})
        if email:
            custom_fields_values.append({"field_code": "EMAIL", "values": [{"value": email}]})
        body = [{"name": name, "custom_fields_values": custom_fields_values or None}]
        return await self._request("POST", "/api/v4/contacts", json_body=body)

    async def find_lead(self, *, query: str) -> dict[str, Any]:
        return await self._request("GET", "/api/v4/leads", params={"query": query})

    async def create_lead(self, *, name: str, price: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if price is not None:
            payload["price"] = int(price)
        return await self._request("POST", "/api/v4/leads", json_body=[payload])

    async def update_lead(self, *, lead_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        payload = {"id": int(lead_id), **fields}
        return await self._request("PATCH", "/api/v4/leads", json_body=[payload])

    async def add_note(self, *, entity_type: str, entity_id: int, text: str) -> dict[str, Any]:
        normalized = (entity_type or "").strip().lower()
        if normalized not in {"lead", "contact", "company"}:
            raise RuntimeError("Unsupported entity_type for note")
        path_entity = f"{normalized}s" if normalized != "company" else "companies"
        return await self._request(
            "POST",
            f"/api/v4/{path_entity}/{int(entity_id)}/notes",
            json_body=[{"note_type": "common", "params": {"text": text}}],
        )

    async def create_task(
        self,
        *,
        text: str,
        complete_till_unix: int,
        entity_type: str,
        entity_id: int,
        responsible_user_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": text,
            "complete_till": int(complete_till_unix),
            "entity_id": int(entity_id),
            "entity_type": (entity_type or "").strip().lower(),
        }
        if responsible_user_id is not None:
            payload["responsible_user_id"] = int(responsible_user_id)
        return await self._request("POST", "/api/v4/tasks", json_body=[payload])

    async def assign_owner(self, *, entity_type: str, entity_id: int, responsible_user_id: int) -> dict[str, Any]:
        normalized = (entity_type or "").strip().lower()
        if normalized not in {"lead", "contact", "company"}:
            raise RuntimeError("Unsupported entity_type for assign_owner")
        path_entity = f"{normalized}s" if normalized != "company" else "companies"
        payload = [{"id": int(entity_id), "responsible_user_id": int(responsible_user_id)}]
        return await self._request("PATCH", f"/api/v4/{path_entity}", json_body=payload)
