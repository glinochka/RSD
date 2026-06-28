"""CRM tool registry with validation and safety controls."""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from .providers.base import CRMProvider
from ..tool_confirmation import TOOL_CONFIRMATION_REQUIRED_HINT, user_has_confirmed_action
from ..tool_registry_core import (
    IdempotencyCache,
    build_idempotency_key,
    build_openai_tool_schema,
    canonical_tool_args,
    filter_allowed_tools,
    parse_tool_arguments,
    tool_args_hash,
)

_SENSITIVE_FIELD_DENYLIST = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "encryption_key",
}
_UPDATE_LEAD_ALLOWED_FIELDS = {
    "name",
    "price",
    "status_id",
    "pipeline_id",
    "responsible_user_id",
    "custom_fields_values",
    "tags_to_add",
    "tags_to_delete",
}
_MAX_UPDATE_LEAD_DEPTH = 4
_MAX_UPDATE_LEAD_COLLECTION_SIZE = 50
_MAX_UPDATE_LEAD_STRING_LENGTH = 512

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
        recent_history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._allowed_tools = filter_allowed_tools(allowed_tools, _TOOL_MODELS)
        self._provider = provider
        self._confirmation_policy = (confirmation_policy or "confirm_risky").strip().lower()
        self._user_message = user_message or ""
        self._recent_history = list(recent_history or [])
        self._agent_id = agent_id
        self._user_external_id = (user_external_id or "").strip() or "anonymous"
        self._crm_provider = getattr(provider, "provider_name", "unknown")
        self._idempotency = IdempotencyCache()

    def tools_for_llm(self) -> list[dict[str, Any]]:
        return [
            build_openai_tool_schema(name, _TOOL_MODELS[name], _TOOL_DESCRIPTIONS[name])
            for name in self._allowed_tools
        ]

    def _requires_confirmation(self, tool_name: str) -> bool:
        policy = self._confirmation_policy
        if policy == "never_confirm":
            return False
        if policy == "always_confirm":
            return tool_name not in _READ_ONLY_TOOLS
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
            if normalized not in _UPDATE_LEAD_ALLOWED_FIELDS:
                raise RuntimeError(f"Field '{key}' is not allowed by update policy")
        self._assert_payload_limits(fields, depth=0)

    def _assert_payload_limits(self, value: Any, *, depth: int) -> None:
        if depth > _MAX_UPDATE_LEAD_DEPTH:
            raise RuntimeError("Payload is too deeply nested")
        if isinstance(value, str):
            if len(value) > _MAX_UPDATE_LEAD_STRING_LENGTH:
                raise RuntimeError("Payload string value is too long")
            return
        if isinstance(value, (int, float, bool)) or value is None:
            return
        if isinstance(value, list):
            if len(value) > _MAX_UPDATE_LEAD_COLLECTION_SIZE:
                raise RuntimeError("Payload list is too large")
            for item in value:
                self._assert_payload_limits(item, depth=depth + 1)
            return
        if isinstance(value, dict):
            if len(value) > _MAX_UPDATE_LEAD_COLLECTION_SIZE:
                raise RuntimeError("Payload object is too large")
            for key, item in value.items():
                key_str = str(key)
                if len(key_str) > 128:
                    raise RuntimeError("Payload key is too long")
                self._assert_payload_limits(item, depth=depth + 1)
            return
        raise RuntimeError("Unsupported payload type")

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if tool_name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{tool_name}' is not allowed")

        model_type = _TOOL_MODELS.get(tool_name)
        if not model_type:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")

        args = parse_tool_arguments(raw_arguments, model_type, tool_name=tool_name)
        self._assert_safe_fields(tool_name, args)

        if self._requires_confirmation(tool_name) and not user_has_confirmed_action(
            self._user_message,
            recent_history=self._recent_history,
        ):
            raise CRMNeedsConfirmationError(TOOL_CONFIRMATION_REQUIRED_HINT)

        canonical = canonical_tool_args(args)
        args_hash = tool_args_hash(canonical)
        self._idempotency.cleanup()
        idempotency_key = build_idempotency_key(
            self._agent_id,
            self._user_external_id,
            tool_name,
            canonical,
        )
        cached = self._idempotency.get(idempotency_key)
        if cached:
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args_hash": args_hash,
                "tool_status": "success",
                "crm_provider": self._crm_provider,
                "latency_ms": 0,
                "idempotent_replay": True,
                "idempotency_key": idempotency_key,
                "result": cached,
            }

        data = args.model_dump()
        started = time.perf_counter()
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

        cached_payload = {"tool": tool_name, "result": result}
        self._idempotency.set(idempotency_key, cached_payload)
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args_hash": args_hash,
            "tool_status": "success",
            "crm_provider": self._crm_provider,
            "latency_ms": latency_ms,
            "idempotency_key": idempotency_key,
            "result": result,
        }
