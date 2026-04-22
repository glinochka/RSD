"""CRM tool registry with validation and safety controls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .providers.base import CRMProvider

_IDEMPOTENCY_TTL_SECONDS = 120
_IDEMPOTENCY_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}

_SENSITIVE_FIELD_DENYLIST = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "encryption_key",
}

_READ_ONLY_TOOLS = {"find_contact", "find_lead"}
_HIGH_RISK_TOOLS = {"update_lead", "assign_owner"}


class CRMNeedsConfirmationError(RuntimeError):
    pass


class _FindContactArgs(BaseModel):
    query: str = Field(..., min_length=1, max_length=256)


class _CreateContactArgs(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=5, max_length=255)


class _FindLeadArgs(BaseModel):
    query: str = Field(..., min_length=1, max_length=256)


class _CreateLeadArgs(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: int | None = Field(default=None, ge=0, le=10_000_000_000)


class _UpdateLeadArgs(BaseModel):
    lead_id: int = Field(..., gt=0)
    fields: dict[str, Any] = Field(..., min_length=1)


class _AddNoteArgs(BaseModel):
    entity_type: str = Field(..., pattern="^(lead|contact|company)$")
    entity_id: int = Field(..., gt=0)
    text: str = Field(..., min_length=1, max_length=4000)


class _CreateTaskArgs(BaseModel):
    text: str = Field(..., min_length=1, max_length=1024)
    complete_till_unix: int = Field(..., gt=0)
    entity_type: str = Field(..., pattern="^(lead|contact|company)$")
    entity_id: int = Field(..., gt=0)
    responsible_user_id: int | None = Field(default=None, gt=0)


class _AssignOwnerArgs(BaseModel):
    entity_type: str = Field(..., pattern="^(lead|contact|company)$")
    entity_id: int = Field(..., gt=0)
    responsible_user_id: int = Field(..., gt=0)


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "find_contact": _FindContactArgs,
    "create_contact": _CreateContactArgs,
    "find_lead": _FindLeadArgs,
    "create_lead": _CreateLeadArgs,
    "update_lead": _UpdateLeadArgs,
    "add_note": _AddNoteArgs,
    "create_task": _CreateTaskArgs,
    "assign_owner": _AssignOwnerArgs,
}

_TOOL_DESCRIPTIONS = {
    "find_contact": "Find contact by query in CRM.",
    "create_contact": "Create a new contact in CRM.",
    "find_lead": "Find lead by query in CRM.",
    "create_lead": "Create a new lead in CRM.",
    "update_lead": "Update lead fields in CRM.",
    "add_note": "Add note to entity (lead/contact/company) in CRM.",
    "create_task": "Create a CRM task linked to entity.",
    "assign_owner": "Assign responsible user to entity.",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup_idempotency_cache() -> None:
    now = _now_utc()
    expired = [key for key, (expires_at, _) in _IDEMPOTENCY_CACHE.items() if expires_at <= now]
    for key in expired:
        _IDEMPOTENCY_CACHE.pop(key, None)


def _has_confirmation_marker(user_message: str) -> bool:
    text = (user_message or "").strip().lower()
    if not text:
        return False
    markers = {"подтверждаю", "подтвердить", "confirm", "подтверждено", "ok, выполняй", "выполняй"}
    return any(marker in text for marker in markers)


class CRMToolRegistry:
    def __init__(
        self,
        *,
        provider: CRMProvider,
        allowed_tools: list[str] | None,
        confirmation_policy: str,
        user_message: str,
        agent_id: int,
        user_external_id: str | None,
    ) -> None:
        requested = [str(tool or "").strip() for tool in (allowed_tools or [])]
        unique = []
        for tool in requested:
            if tool and tool in _TOOL_MODELS and tool not in unique:
                unique.append(tool)
        self._allowed_tools = unique or list(_TOOL_MODELS.keys())
        self._provider = provider
        self._confirmation_policy = (confirmation_policy or "confirm_risky").strip().lower()
        self._user_message = user_message or ""
        self._agent_id = agent_id
        self._user_external_id = (user_external_id or "").strip() or "anonymous"

    def tools_for_llm(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for name in self._allowed_tools:
            model = _TOOL_MODELS[name]
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": _TOOL_DESCRIPTIONS[name],
                        "parameters": model.model_json_schema(),
                    },
                }
            )
        return tools

    def _requires_confirmation(self, tool_name: str) -> bool:
        policy = self._confirmation_policy
        if policy == "never_confirm":
            return False
        if policy == "always_confirm":
            return tool_name not in _READ_ONLY_TOOLS
        # confirm_risky (default)
        return tool_name in _HIGH_RISK_TOOLS

    def _assert_safe_fields(self, tool_name: str, args: BaseModel) -> None:
        if tool_name != "update_lead":
            return
        payload = args.model_dump()
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            return
        for key in fields:
            normalized = str(key or "").strip().lower()
            if normalized in _SENSITIVE_FIELD_DENYLIST:
                raise RuntimeError(f"Field '{key}' is blocked by safety policy")

    def _idempotency_key(self, tool_name: str, model: BaseModel) -> str:
        canonical_args = json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True)
        raw = f"{self._agent_id}:{self._user_external_id}:{tool_name}:{canonical_args}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if tool_name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{tool_name}' is not allowed")

        model_type = _TOOL_MODELS.get(tool_name)
        if not model_type:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")

        try:
            payload = json.loads(raw_arguments or "{}")
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON arguments for tool '{tool_name}': {exc}")

        try:
            args = model_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"Validation failed for tool '{tool_name}': {exc}")

        self._assert_safe_fields(tool_name, args)

        if self._requires_confirmation(tool_name) and not _has_confirmation_marker(self._user_message):
            raise CRMNeedsConfirmationError(
                "Для выполнения этого действия нужно явное подтверждение. "
                "Попросите пользователя написать: 'подтверждаю'."
            )

        _cleanup_idempotency_cache()
        idempotency_key = self._idempotency_key(tool_name, args)
        cached = _IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached:
            _, value = cached
            return {
                "ok": True,
                "idempotent_replay": True,
                "idempotency_key": idempotency_key,
                "result": value,
            }

        data = args.model_dump()
        if tool_name == "find_contact":
            result = await self._provider.find_contact(**data)
        elif tool_name == "create_contact":
            result = await self._provider.create_contact(**data)
        elif tool_name == "find_lead":
            result = await self._provider.find_lead(**data)
        elif tool_name == "create_lead":
            result = await self._provider.create_lead(**data)
        elif tool_name == "update_lead":
            result = await self._provider.update_lead(**data)
        elif tool_name == "add_note":
            result = await self._provider.add_note(**data)
        elif tool_name == "create_task":
            result = await self._provider.create_task(**data)
        elif tool_name == "assign_owner":
            result = await self._provider.assign_owner(**data)
        else:
            raise RuntimeError(f"Tool '{tool_name}' is not supported")

        _IDEMPOTENCY_CACHE[idempotency_key] = (
            _now_utc() + timedelta(seconds=_IDEMPOTENCY_TTL_SECONDS),
            {"tool": tool_name, "result": result},
        )
        return {
            "ok": True,
            "idempotency_key": idempotency_key,
            "result": result,
        }
