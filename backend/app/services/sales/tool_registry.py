"""Sales tool registry with validation and safety controls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError

_IDEMPOTENCY_TTL_SECONDS = 120
_IDEMPOTENCY_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
_MAX_RAW_ARGUMENTS_BYTES = 16_000
_HIGH_RISK_TOOLS = {"schedule_dm", "create_crm_lead", "mark_contacted"}


class SalesNeedsConfirmationError(RuntimeError):
    pass


class _ScheduleDmArgs(BaseModel):
    text: str = Field(..., min_length=1, max_length=1200)
    target_user_external_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_chat_id: int | None = Field(default=None)


class _SkipLeadArgs(BaseModel):
    reason_code: str = Field(..., min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class _RecordLeadSignalArgs(BaseModel):
    signal_type: str = Field(..., min_length=2, max_length=64)
    score: float = Field(..., ge=0.0, le=1.0)
    details: str | None = Field(default=None, max_length=300)


class _CreateCrmLeadArgs(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    note: str | None = Field(default=None, max_length=2000)


class _MarkContactedArgs(BaseModel):
    channel: str = Field(
        default="telegram_userbot",
        pattern="^(telegram_userbot|whatsapp_userbot)$",
    )
    campaign_id: str | None = Field(default=None, max_length=128)


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "schedule_dm": _ScheduleDmArgs,
    "skip_lead": _SkipLeadArgs,
    "record_lead_signal": _RecordLeadSignalArgs,
    "create_crm_lead": _CreateCrmLeadArgs,
    "mark_contacted": _MarkContactedArgs,
}

_TOOL_DESCRIPTIONS = {
    "schedule_dm": "Queue a direct message outreach for a qualified lead.",
    "skip_lead": "Skip lead processing and persist reason code.",
    "record_lead_signal": "Store a lead qualification signal and score.",
    "create_crm_lead": "Create a lead in CRM (if CRM integration is available).",
    "mark_contacted": "Mark lead/contact as contacted in outreach state machine.",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cleanup_idempotency_cache() -> None:
    now = _now_utc()
    expired = [key for key, (expires_at, _) in _IDEMPOTENCY_CACHE.items() if expires_at <= now]
    for key in expired:
        _IDEMPOTENCY_CACHE.pop(key, None)


from ..tool_confirmation import TOOL_CONFIRMATION_REQUIRED_HINT, user_has_confirmed_action


class SalesToolRegistry:
    def __init__(
        self,
        *,
        allowed_tools: list[str] | None,
        confirmation_policy: str,
        user_message: str,
        agent_id: int | None,
        user_external_id: str | None,
        mode: str,
        telegram_peer_access_hash: int | None = None,
        source_channel: str | None = None,
        recent_history: list[dict[str, Any]] | None = None,
    ) -> None:
        requested = [str(tool or "").strip() for tool in (allowed_tools or [])]
        unique: list[str] = []
        for tool in requested:
            if tool and tool in _TOOL_MODELS and tool not in unique:
                unique.append(tool)
        self._allowed_tools = unique or list(_TOOL_MODELS.keys())
        self._confirmation_policy = (confirmation_policy or "confirm_risky").strip().lower()
        self._user_message = user_message or ""
        self._recent_history = list(recent_history or [])
        self._agent_id = int(agent_id or 0)
        self._user_external_id = (user_external_id or "").strip() or "anonymous"
        self._mode = (mode or "draft_only").strip().lower()
        self._telegram_peer_access_hash: int | None = None
        if telegram_peer_access_hash is not None:
            try:
                h = int(telegram_peer_access_hash)
                if h != 0:
                    self._telegram_peer_access_hash = h
            except (TypeError, ValueError):
                self._telegram_peer_access_hash = None
        ch = (source_channel or "telegram_userbot").strip().lower()
        if ch == "whatsapp_userbot":
            self._outbound_channel = "whatsapp_userbot"
        else:
            self._outbound_channel = "telegram_userbot"

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
            return tool_name != "record_lead_signal"
        return tool_name in _HIGH_RISK_TOOLS

    def _canonical_args(self, model: BaseModel) -> str:
        return json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True)

    def _idempotency_key(self, tool_name: str, canonical_args: str) -> str:
        raw = f"{self._agent_id}:{self._user_external_id}:{tool_name}:{canonical_args}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _tool_args_hash(canonical_args: str) -> str:
        return hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if len((raw_arguments or "").encode("utf-8")) > _MAX_RAW_ARGUMENTS_BYTES:
            raise RuntimeError("Tool arguments payload is too large")
        if tool_name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{tool_name}' is not allowed")

        model_type = _TOOL_MODELS.get(tool_name)
        if not model_type:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")

        try:
            payload = json.loads(raw_arguments or "{}")
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON arguments for tool '{tool_name}': {exc}") from None

        try:
            args = model_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"Validation failed for tool '{tool_name}': {exc}") from None

        if self._requires_confirmation(tool_name) and not user_has_confirmed_action(
            self._user_message,
            recent_history=self._recent_history,
        ):
            raise SalesNeedsConfirmationError(TOOL_CONFIRMATION_REQUIRED_HINT)

        canonical_args = self._canonical_args(args)
        tool_args_hash = self._tool_args_hash(canonical_args)
        _cleanup_idempotency_cache()
        idempotency_key = self._idempotency_key(tool_name, canonical_args)
        cached = _IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached:
            _, value = cached
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args_hash": tool_args_hash,
                "tool_status": "success",
                "latency_ms": 0,
                "idempotent_replay": True,
                "idempotency_key": idempotency_key,
                "result": value,
            }

        data = args.model_dump()
        started = time.perf_counter()
        
        if tool_name == "schedule_dm":
            # Enqueue DM for async sending
            from .dm_queue_service import get_dm_queue_service
            
            queue_service = get_dm_queue_service()
            target_uid = data.get("target_user_external_id") or self._user_external_id
            source_cid = str(data.get("source_chat_id") or "global")
            
            meta: dict[str, Any] = {
                "mode": self._mode,
                "qualification": "auto" if self._mode == "auto" else "manual",
                "channel": self._outbound_channel,
            }
            if self._telegram_peer_access_hash is not None:
                meta["telegram_peer_access_hash"] = self._telegram_peer_access_hash
            await queue_service.enqueue_dm(
                agent_id=self._agent_id,
                target_user_external_id=target_uid,
                source_chat_id=source_cid,
                message_text=data.get("text", ""),
                metadata=meta,
            )
            if self._agent_id and target_uid:
                from .contact_pool import register_user_in_agent_contact_pool

                await register_user_in_agent_contact_pool(
                    agent_id=self._agent_id,
                    user_external_id=target_uid,
                    source_chat_id=source_cid,
                    origin="outbound_schedule_dm",
                )
            
            if self._mode == "auto":
                status = "sent_auto"
            else:
                status = "draft_requires_review"
            result = {"queued": True, "status": status, "payload": data}
            
        elif tool_name == "skip_lead":
            status = "skipped"
            result = {"skipped": True, "payload": data}
        elif tool_name == "record_lead_signal":
            status = "recorded"
            result = {"recorded": True, "payload": data}
        elif tool_name == "create_crm_lead":
            status = "crm_lead_created"
            result = {"crm_lead_created": True, "payload": data}
        elif tool_name == "mark_contacted":
            status = "marked_contacted"
            result = {"marked": True, "payload": data}
        else:
            raise RuntimeError(f"Tool '{tool_name}' is not supported")
            
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        _IDEMPOTENCY_CACHE[idempotency_key] = (
            _now_utc() + timedelta(seconds=_IDEMPOTENCY_TTL_SECONDS),
            {"tool": tool_name, "result": result},
        )
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args_hash": tool_args_hash,
            "tool_status": status,
            "latency_ms": latency_ms,
            "idempotency_key": idempotency_key,
            "result": result,
        }

