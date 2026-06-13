"""Configurable HTTP integrations exposed as LLM tools (crm_admin)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import AgentHttpIntegration
from ...utils.crypto import decrypt_crm_credentials
from .errors import HttpIntegrationNeedsConfirmationError, HttpIntegrationValidationError
from .executor import (
    _has_confirmation_marker,
    assert_args_match_schema,
    assert_safe_relative_path,
    execute_http_tool,
    merge_auth_headers,
    validate_parameters_schema,
)

logger = logging.getLogger(__name__)

_MAX_TOOLS_TOTAL = 28
_MAX_RAW_ARGUMENTS_BYTES = 24_000
_TOOL_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,48}$")


@dataclass
class _ToolBinding:
    row_id: int
    integration_slug: str
    method: str
    path_template: str


def composite_tool_name(row_id: int, tool_slug: str) -> str:
    name = f"external_i{row_id}__{tool_slug}"
    if len(name) > 64:
        raise HttpIntegrationValidationError(
            "Слишком длинное имя инструмента (вместе с префиксом должно быть ≤ 64 символов)."
        )
    return name


def validate_integration_config_dict(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate plaintext integration bundle (before encryption). Raises HttpIntegrationValidationError."""
    base_url = str(bundle.get("base_url") or "").strip().rstrip("/")
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        raise HttpIntegrationValidationError("base_url must start with http:// or https://")
    if len(base_url) > 2048:
        raise HttpIntegrationValidationError("base_url is too long")
    timeout_raw = bundle.get("timeout_seconds", 25)
    try:
        timeout_seconds = float(timeout_raw)
    except (TypeError, ValueError):
        raise HttpIntegrationValidationError("timeout_seconds must be a number") from None
    if timeout_seconds < 3 or timeout_seconds > 120:
        raise HttpIntegrationValidationError("timeout_seconds must be between 3 and 120")

    dh = bundle.get("default_headers")
    if dh is None:
        default_headers: dict[str, str] = {}
    elif isinstance(dh, dict):
        default_headers = {str(k): str(v) for k, v in dh.items() if str(k)}
    else:
        raise HttpIntegrationValidationError("default_headers must be an object with string keys/values")

    auth = bundle.get("auth")
    auth_dict: dict[str, Any] = auth if isinstance(auth, dict) else {"type": "none"}
    merge_auth_headers(auth_cfg=auth_dict, base_headers=default_headers)  # dry-run validates auth shape

    tools_raw = bundle.get("tools")
    if not isinstance(tools_raw, list) or not tools_raw:
        raise HttpIntegrationValidationError("tools must be a non-empty array")
    if len(tools_raw) > 16:
        raise HttpIntegrationValidationError("At most 16 tools per integration are allowed")

    seen: set[str] = set()
    normalized_tools: list[dict[str, Any]] = []
    for idx, raw_tool in enumerate(tools_raw):
        if not isinstance(raw_tool, dict):
            raise HttpIntegrationValidationError(f"tools[{idx}] must be an object")
        tname = str(raw_tool.get("name") or "").strip()
        if not _TOOL_SLUG_RE.match(tname):
            raise HttpIntegrationValidationError(
                f"tools[{idx}].name must be snake_case matching [a-z][a-z0-9_]{{0,48}}"
            )
        try:
            composite_tool_name(2_147_483_647, tname)
        except HttpIntegrationValidationError as exc:
            raise HttpIntegrationValidationError(f"tools[{idx}].name: {exc}") from exc
        if tname in seen:
            raise HttpIntegrationValidationError(f"Duplicate tool name: {tname}")
        seen.add(tname)

        description = str(raw_tool.get("description") or "").strip()
        if not description or len(description) > 2000:
            raise HttpIntegrationValidationError(f"tools[{idx}].description is required (max 2000 chars)")

        method = str(raw_tool.get("method") or "GET").strip().upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise HttpIntegrationValidationError(f"tools[{idx}].method is invalid")

        path_t = assert_safe_relative_path(str(raw_tool.get("path") or "").strip())

        params = raw_tool.get("parameters")
        if not isinstance(params, dict):
            raise HttpIntegrationValidationError(f"tools[{idx}].parameters must be a JSON Schema object dict")
        validate_parameters_schema(params)

        rc = raw_tool.get("requires_confirmation")
        requires_confirmation: bool | None
        if rc is None:
            requires_confirmation = None
        elif isinstance(rc, bool):
            requires_confirmation = rc
        else:
            raise HttpIntegrationValidationError(f"tools[{idx}].requires_confirmation must be boolean or null")

        normalized_tools.append(
            {
                "name": tname,
                "description": description,
                "method": method,
                "path": path_t,
                "requires_confirmation": requires_confirmation,
                "parameters": params,
            }
        )

    out = {
        "base_url": base_url,
        "timeout_seconds": timeout_seconds,
        "default_headers": default_headers,
        "auth": auth_dict,
        "tools": normalized_tools,
    }
    raw_preview = json.dumps(out, ensure_ascii=False).encode("utf-8")
    if len(raw_preview) > 120_000:
        raise HttpIntegrationValidationError("Integration configuration is too large")
    return out


class HttpIntegrationToolRegistry:
    def __init__(
        self,
        *,
        bindings: dict[str, _ToolBinding],
        bundles_by_row: dict[int, dict[str, Any]],
        user_message: str,
    ) -> None:
        self._bindings = bindings
        self._bundles_by_row = bundles_by_row
        self._user_message = user_message or ""

    def tools_for_llm(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for llm_name, binding in sorted(self._bindings.items(), key=lambda kv: kv[0]):
            bundle = self._bundles_by_row.get(binding.row_id) or {}
            for t in bundle.get("tools") or []:
                if composite_tool_name(binding.row_id, str(t["name"])) != llm_name:
                    continue
                params = t.get("parameters") or {}
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": llm_name,
                            "description": str(t.get("description") or ""),
                            "parameters": params,
                        },
                    }
                )
                break
        return tools

    def has_tool(self, name: str) -> bool:
        return name in self._bindings

    def llm_tool_names(self) -> frozenset[str]:
        return frozenset(self._bindings.keys())

    @staticmethod
    def _canonical_args(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _tool_args_hash(canonical: str) -> str:
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _confirmation_required(self, binding: _ToolBinding, bundle_tool: dict[str, Any]) -> bool:
        explicit = bundle_tool.get("requires_confirmation")
        if isinstance(explicit, bool):
            return explicit
        return binding.method.upper() != "GET"

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if len((raw_arguments or "").encode("utf-8")) > _MAX_RAW_ARGUMENTS_BYTES:
            raise HttpIntegrationValidationError("Tool arguments are too large")
        binding = self._bindings.get(tool_name)
        if binding is None:
            raise RuntimeError(f"Unknown HTTP integration tool '{tool_name}'")

        bundle = self._bundles_by_row.get(binding.row_id)
        if not bundle:
            raise RuntimeError("Integration bundle is missing")

        tool_spec = next((t for t in bundle.get("tools") or [] if str(t.get("name")) == binding.integration_slug), None)
        if not tool_spec:
            raise RuntimeError("Tool specification not found")

        try:
            args = json.loads(raw_arguments or "{}")
        except Exception as exc:
            raise HttpIntegrationValidationError(f"Invalid JSON tool arguments: {exc}") from exc
        if not isinstance(args, dict):
            raise HttpIntegrationValidationError("Tool arguments must be a JSON object")

        schema = tool_spec.get("parameters") if isinstance(tool_spec.get("parameters"), dict) else {}
        assert_args_match_schema(schema, args)

        if self._confirmation_required(binding, tool_spec) and not _has_confirmation_marker(self._user_message):
            raise HttpIntegrationNeedsConfirmationError(
                "Для этого действия внешней системы нужно явное подтверждение. "
                "Попросите пользователя написать: «подтверждаю»."
            )

        canonical = self._canonical_args(args)
        tool_args_hash = self._tool_args_hash(canonical)
        headers = merge_auth_headers(
            auth_cfg=bundle.get("auth") if isinstance(bundle.get("auth"), dict) else {},
            base_headers=(
                {str(k): str(v) for k, v in (bundle.get("default_headers") or {}).items()}
                if isinstance(bundle.get("default_headers"), dict)
                else {}
            ),
        )
        timeout_sec = float(bundle.get("timeout_seconds") or 25)
        exec_result = await execute_http_tool(
            base_url=str(bundle["base_url"]),
            method=binding.method,
            path_template=binding.path_template,
            headers=headers,
            args=args,
            timeout_seconds=timeout_sec,
        )
        ok = bool(exec_result.get("ok"))
        tool_status = "success" if ok else "error"
        latency_ms = int(exec_result.get("latency_ms") or 0)
        nested = exec_result.get("result")
        return {
            "ok": ok,
            "tool_name": tool_name,
            "tool_args_hash": tool_args_hash,
            "tool_status": tool_status,
            "crm_provider": "http_integration",
            "latency_ms": latency_ms,
            "result": nested,
            "http_status": exec_result.get("http_status"),
            "error": None if ok else exec_result.get("error") or nested,
        }


async def load_http_integration_registry(
    *,
    agent_id: int,
    enabled: bool,
    name_allowlist: list[str] | None,
    user_message: str,
) -> HttpIntegrationToolRegistry | None:
    if not enabled or not agent_id:
        return None

    bindings: dict[str, _ToolBinding] = {}
    bundles_by_row: dict[int, dict[str, Any]] = {}
    allowed = (
        {str(x or "").strip().lower() for x in name_allowlist if str(x or "").strip()}
        if name_allowlist
        else None
    )

    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                (
                    await session.execute(
                        select(AgentHttpIntegration)
                        .where(
                            AgentHttpIntegration.agent_id == agent_id,
                            AgentHttpIntegration.is_active.is_(True),
                        )
                        .order_by(AgentHttpIntegration.id.asc())
                    )
                )
                .scalars()
                .all()
            )

    tools_added = 0
    for row in rows:
        slug = (row.name or "").strip().lower()
        if allowed is not None and slug not in allowed:
            continue
        try:
            decrypted, _ = decrypt_crm_credentials(row.encrypted_config)
            loaded = json.loads(decrypted)
        except Exception:
            logger.exception("http_integration decrypt/parse failed agent_id=%s row_id=%s", agent_id, row.id)
            continue
        if not isinstance(loaded, dict):
            continue
        try:
            bundle = validate_integration_config_dict(loaded)
        except HttpIntegrationValidationError:
            logger.exception("Invalid http_integration bundle stored for agent_id=%s row_id=%s", agent_id, row.id)
            continue

        bundles_by_row[int(row.id)] = bundle

        for t in bundle["tools"]:
            if tools_added >= _MAX_TOOLS_TOTAL:
                logger.warning(
                    "http_integration tool limit reached (%s); skipping extras for agent_id=%s",
                    _MAX_TOOLS_TOTAL,
                    agent_id,
                )
                break
            tslug = str(t["name"])
            llm_tool = composite_tool_name(int(row.id), tslug)
            bindings[llm_tool] = _ToolBinding(
                row_id=int(row.id),
                integration_slug=tslug,
                method=str(t["method"]),
                path_template=str(t["path"]),
            )
            tools_added += 1
        if tools_added >= _MAX_TOOLS_TOTAL:
            break

    if not bindings:
        return None
    return HttpIntegrationToolRegistry(
        bindings=bindings,
        bundles_by_row=bundles_by_row,
        user_message=user_message,
    )
