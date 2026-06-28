"""Shared plumbing for domain tool registries (idempotency, parsing, OpenAI schemas)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)

DEFAULT_IDEMPOTENCY_TTL_SECONDS = 120
DEFAULT_MAX_RAW_ARGUMENTS_BYTES = 16_000
HTTP_INTEGRATION_MAX_RAW_ARGUMENTS_BYTES = 24_000


def now_utc() -> datetime:
    """Naive UTC datetime for idempotency expiry (sales, booking, applications)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def canonical_tool_args(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True)


def canonical_tool_args_dict(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def tool_args_hash(canonical_args: str) -> str:
    return hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()


def build_idempotency_key(
    agent_id: int,
    user_external_id: str,
    tool_name: str,
    canonical_args: str,
) -> str:
    raw = f"{agent_id}:{user_external_id}:{tool_name}:{canonical_args}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_idempotency_key_from_payload(
    agent_id: int,
    user_external_id: str,
    tool_name: str,
    args: dict[str, Any],
) -> str:
    payload = json.dumps(
        {"agent_id": agent_id, "user": user_external_id, "tool": tool_name, "args": args},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def filter_allowed_tools(
    allowed_tools: list[str] | None,
    models: dict[str, type[BaseModel]],
) -> list[str]:
    requested = [str(tool or "").strip() for tool in (allowed_tools or [])]
    unique: list[str] = []
    for tool in requested:
        if tool and tool in models and tool not in unique:
            unique.append(tool)
    return unique or list(models.keys())


def build_openai_tool_schema(
    name: str,
    model: type[BaseModel],
    description: str,
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": model.model_json_schema(),
        },
    }


def tools_for_llm_from_models(
    allowed_tools: list[str],
    models: dict[str, type[BaseModel]],
    descriptions: dict[str, str],
) -> list[dict[str, Any]]:
    return [
        build_openai_tool_schema(name, models[name], descriptions.get(name, name))
        for name in allowed_tools
    ]


def parse_tool_arguments(
    raw: str,
    model_type: type[TModel],
    *,
    tool_name: str,
    max_bytes: int = DEFAULT_MAX_RAW_ARGUMENTS_BYTES,
) -> TModel:
    if len((raw or "").encode("utf-8")) > max_bytes:
        raise RuntimeError("Tool arguments payload is too large")
    try:
        payload = json.loads(raw or "{}")
    except Exception as exc:
        raise RuntimeError(f"Invalid JSON arguments for tool '{tool_name}': {exc}") from None
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(f"Validation failed for tool '{tool_name}': {exc}") from None


class IdempotencyCache:
    """Per-registry TTL cache; not shared across domains or instances."""

    def __init__(self, ttl_seconds: int = DEFAULT_IDEMPOTENCY_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[datetime, dict[str, Any]]] = {}

    def cleanup(self) -> None:
        now = now_utc()
        expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at <= now_utc():
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._entries[key] = (
            now_utc() + timedelta(seconds=self._ttl_seconds),
            value,
        )


@dataclass
class ToolExecutionResult:
    ok: bool
    data: Any
    latency_ms: int
    error: str | None = None
