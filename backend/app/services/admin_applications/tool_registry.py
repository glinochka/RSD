"""LLM tool registry for application intake workflow."""
from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ..tool_registry_core import (
    IdempotencyCache,
    build_idempotency_key_from_payload,
    build_openai_tool_schema,
    filter_allowed_tools,
)
from .fields import fields_schema_for_prompt
from .service import get_admin_application_service

_IDEMPOTENCY_PROTECTED_TOOLS = {"create_application"}


class _GetApplicationSchemaArgs(BaseModel):
    pass


class _CreateApplicationArgs(BaseModel):
    client_name: str | None = Field(default=None, max_length=128)
    fields: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)


class _ListClientApplicationsArgs(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(new|in_progress|completed|rejected|cancelled)$",
    )
    limit: int = Field(default=10, gt=0, le=50)


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "get_application_schema": _GetApplicationSchemaArgs,
    "create_application": _CreateApplicationArgs,
    "list_client_applications": _ListClientApplicationsArgs,
}

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_application_schema": (
        "Вернуть схему полей заявки: какие данные нужно собрать у клиента перед отправкой."
    ),
    "create_application": (
        "Создать заявку после того, как клиент подтвердил все обязательные поля. "
        "Передай собранные значения в fields (ключи из схемы)."
    ),
    "list_client_applications": (
        "Список заявок текущего клиента в этом чате (статус, дата, поля)."
    ),
}


class AdminApplicationToolRegistry:
    def __init__(
        self,
        *,
        agent_id: int,
        user_external_id: str | None,
        source_channel: str,
        template_config: dict[str, Any] | None,
        allowed_tools: list[str] | None = None,
    ) -> None:
        self._allowed_tools = filter_allowed_tools(allowed_tools, _TOOL_MODELS)
        self._agent_id = agent_id
        self._user_external_id = (user_external_id or "").strip() or "anonymous"
        self._source_channel = (source_channel or "telegram").strip().lower() or "telegram"
        self._template_config = template_config if isinstance(template_config, dict) else {}
        self._fields_schema = get_admin_application_service().get_fields_schema(self._template_config)
        self._idempotency = IdempotencyCache()

    def tools_for_llm(self) -> list[dict[str, Any]]:
        return [
            build_openai_tool_schema(name, _TOOL_MODELS[name], _TOOL_DESCRIPTIONS.get(name, name))
            for name in self._allowed_tools
        ]

    def has_tool(self, name: str) -> bool:
        return str(name or "").strip() in self._allowed_tools

    async def execute_tool(self, tool_name: str, raw_arguments: Any) -> dict[str, Any]:
        started = time.perf_counter()
        name = str(tool_name or "").strip()
        if name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{name}' is not allowed")

        if isinstance(raw_arguments, str):
            try:
                parsed_args = json.loads(raw_arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError("tool arguments must be valid JSON") from exc
        elif isinstance(raw_arguments, dict):
            parsed_args = raw_arguments
        else:
            parsed_args = {}

        try:
            args_model = _TOOL_MODELS[name].model_validate(parsed_args)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        args_dict = args_model.model_dump()

        idem_key: str | None = None
        if name in _IDEMPOTENCY_PROTECTED_TOOLS:
            self._idempotency.cleanup()
            idem_key = build_idempotency_key_from_payload(
                self._agent_id,
                self._user_external_id,
                name,
                args_dict,
            )
            cached = self._idempotency.get(idem_key)
            if cached:
                replay = dict(cached)
                replay["idempotent_replay"] = True
                replay["idempotency_key"] = idem_key
                return replay

        from ...alembic.database import async_session_maker

        result: Any
        if name == "get_application_schema":
            result = {
                "fields": self._fields_schema,
                "schema_hint": fields_schema_for_prompt(self._fields_schema),
            }
        elif name == "create_application":
            async with async_session_maker() as session:
                async with session.begin():
                    result = await get_admin_application_service().create_application(
                        session,
                        agent_id=self._agent_id,
                        template_config=self._template_config,
                        client_external_id=self._user_external_id,
                        client_name=args_dict.get("client_name"),
                        fields=args_dict.get("fields"),
                        source_channel=self._source_channel,
                        notes=args_dict.get("notes"),
                    )
        elif name == "list_client_applications":
            async with async_session_maker() as session:
                result = await get_admin_application_service().list_applications(
                    session,
                    agent_id=self._agent_id,
                    client_external_id=self._user_external_id,
                    status=args_dict.get("status"),
                    limit=args_dict.get("limit") or 10,
                )
        else:
            raise RuntimeError(f"Tool '{name}' is not implemented")

        latency_ms = int((time.perf_counter() - started) * 1000)
        payload = {
            "ok": True,
            "tool_status": "success",
            "result": result,
            "latency_ms": latency_ms,
            "idempotent_replay": False,
            "idempotency_key": idem_key,
            "tool_args_summary": json.dumps(args_dict, ensure_ascii=False)[:500],
        }
        if idem_key and name in _IDEMPOTENCY_PROTECTED_TOOLS:
            self._idempotency.set(idem_key, dict(payload))
        return payload
