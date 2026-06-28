"""Sales tool registry with validation and safety controls."""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

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
        pattern="^(telegram_userbot|whatsapp_userbot|max_userbot)$",
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
        self._allowed_tools = filter_allowed_tools(allowed_tools, _TOOL_MODELS)
        self._confirmation_policy = (confirmation_policy or "confirm_risky").strip().lower()
        self._user_message = user_message or ""
        self._recent_history = list(recent_history or [])
        self._agent_id = int(agent_id or 0)
        self._user_external_id = (user_external_id or "").strip() or "anonymous"
        self._mode = (mode or "draft_only").strip().lower()
        self._idempotency = IdempotencyCache()
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
        elif ch == "max_userbot":
            self._outbound_channel = "max_userbot"
        else:
            self._outbound_channel = "telegram_userbot"

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
            return tool_name != "record_lead_signal"
        return tool_name in _HIGH_RISK_TOOLS

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if tool_name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{tool_name}' is not allowed")

        model_type = _TOOL_MODELS.get(tool_name)
        if not model_type:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")

        args = parse_tool_arguments(raw_arguments, model_type, tool_name=tool_name)

        if self._requires_confirmation(tool_name) and not user_has_confirmed_action(
            self._user_message,
            recent_history=self._recent_history,
        ):
            raise SalesNeedsConfirmationError(TOOL_CONFIRMATION_REQUIRED_HINT)

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
                "latency_ms": 0,
                "idempotent_replay": True,
                "idempotency_key": idempotency_key,
                "result": cached,
            }

        data = args.model_dump()
        started = time.perf_counter()

        if tool_name == "schedule_dm":
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
        cached_payload = {"tool": tool_name, "result": result}
        self._idempotency.set(idempotency_key, cached_payload)
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args_hash": args_hash,
            "tool_status": status,
            "latency_ms": latency_ms,
            "idempotency_key": idempotency_key,
            "result": result,
        }
