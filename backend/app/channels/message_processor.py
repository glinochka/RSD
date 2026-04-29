"""Unified message processing for channel managers."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentAnalyticsMessage, AgentFrozenUser, User
from ..services.qa_handoff_service import EscalationType as QAEscalationType, get_qa_handoff_service
from ..services.template_runtime import EscalationType, get_template_runtime
from ..utils.pii import redact_pii_text
logger = logging.getLogger(__name__)
MAX_INT32 = 2_147_483_647


class Channel(str, Enum):
    TELEGRAM = "telegram"
    TELEGRAM_USERBOT = "telegram_userbot"
    MAX_BOT = "max_bot"
    MAX_USERBOT = "max_userbot"
    WHATSAPP_USERBOT = "whatsapp_userbot"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED_USER = "blocked_user"
    EXPIRED_SUBSCRIPTION = "expired_subscription"
    WELCOME = "welcome"
    ERROR = "error"


@dataclass
class MessageRequest:
    bot_id: int
    query: str
    user_external_id: str
    channel: Channel
    system_prompt: str = ""
    welcome_message: str | None = None
    process_start_with_llm: bool = False
    user_display_name: str | None = None
    telegram_peer_access_hash: int | None = None
    skip_chat_portrait_update: bool = False
    runtime_context: dict[str, object] | None = None


@dataclass
class MessageResponse:
    text: str
    status: ProcessingStatus


class MessageProcessor:
    @staticmethod
    def _parse_template_config(raw: str | None) -> dict | None:
        if not raw or not str(raw).strip():
            return None
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            return None
        return None

    @staticmethod
    def _normalize_user_external_id(channel: Channel, user_external_id: str) -> str:
        uid = (user_external_id or "").strip()
        if channel == Channel.WHATSAPP_USERBOT:
            if "@" in uid:
                return uid.lower()
            digits = "".join(ch for ch in uid if ch.isdigit())
            if digits:
                return f"{digits}@s.whatsapp.net"
            return uid.lower()
        return uid

    @staticmethod
    def _summarize_tool_event(event: dict) -> str:
        tool_name = str(event.get("tool_name") or "unknown")
        status = str(event.get("tool_status") or "unknown")
        latency_ms = int(event.get("latency_ms") or 0)
        provider = str(event.get("crm_provider") or "unknown")
        replay = bool(event.get("idempotent_replay"))
        error = redact_pii_text(str(event.get("error") or "")).strip()
        parts = [
            f"tool={tool_name}",
            f"status={status}",
            f"latency_ms={latency_ms}",
            f"crm_provider={provider}",
            f"idempotent_replay={str(replay).lower()}",
        ]
        if error:
            parts.append(f"error={error}")
        return " ".join(parts)

    async def process(self, request: MessageRequest) -> MessageResponse:
        try:
            normalized_user_external_id = self._normalize_user_external_id(
                request.channel,
                request.user_external_id,
            )
            resolved_agent = await self._resolve_agent(request.bot_id)
            if not resolved_agent:
                return MessageResponse(
                    text="⚠️ Агент не найден.",
                    status=ProcessingStatus.ERROR,
                )

            if not await self._is_subscription_valid(resolved_agent.id):
                return MessageResponse(
                    text=(
                        "⚠️ Извините, но этот бот временно недоступен.\n"
                        "Владельцу бота необходимо проверить статус своей подписки."
                    ),
                    status=ProcessingStatus.EXPIRED_SUBSCRIPTION,
                )

            if await self._is_user_frozen(resolved_agent.id, normalized_user_external_id):
                return MessageResponse(
                    text=(
                        "Доступ к этому агенту для вас временно ограничен владельцем. "
                        "Если это ошибка, обратитесь в поддержку."
                    ),
                    status=ProcessingStatus.BLOCKED_USER,
                )

            if (
                request.query.strip() == "/start"
                and request.channel == Channel.TELEGRAM
                and not request.process_start_with_llm
            ):
                return MessageResponse(
                    text=request.welcome_message or "Здравствуйте! Чем я могу вам помочь?",
                    status=ProcessingStatus.WELCOME,
                )

            await self._log_message(
                agent_id=resolved_agent.id,
                analytics_namespace_id=resolved_agent.bot_id or resolved_agent.id,
                role="user",
                message_text=request.query,
                user_external_id=normalized_user_external_id,
                user_display_name=request.user_display_name,
                channel=request.channel.value,
                telegram_peer_access_hash=request.telegram_peer_access_hash,
            )
            template_config = self._parse_template_config(resolved_agent.template_config)
            normalized_template = str(resolved_agent.template_type or "qa").strip().lower()
            portrait_enabled = bool((template_config or {}).get("enable_chat_portrait", True))
            if normalized_template == "content_factory":
                portrait_enabled = False
            if request.skip_chat_portrait_update:
                portrait_enabled = False
            chat_portrait = ""
            if portrait_enabled:
                chat_portrait = await get_template_runtime().update_chat_portrait(
                    agent_id=resolved_agent.id,
                    analytics_namespace_id=resolved_agent.bot_id or resolved_agent.id,
                    user_external_id=normalized_user_external_id,
                    source_channel=request.channel.value,
                    user_message=request.query,
                    base_prompt=request.system_prompt or (resolved_agent.system_prompt or ""),
                    template_config=template_config,
                )

            execution = await get_template_runtime().execute(
                template_type=resolved_agent.template_type,
                prompt=request.system_prompt or (resolved_agent.system_prompt or ""),
                user_message=request.query,
                knowledge_scope_id=resolved_agent.bot_id or resolved_agent.id,
                agent_id=resolved_agent.id,
                user_external_id=normalized_user_external_id,
                template_config=template_config,
                source_channel=request.channel.value,
                chat_portrait=chat_portrait,
                runtime_context=request.runtime_context or {},
            )
            answer = execution.answer
            handoff_applied = False
            escalation_type_applied: str | None = None
            if execution.requires_owner_handoff and normalized_template == "qa":
                qa_escalation_type = (
                    QAEscalationType.FREEZE_CHAT
                    if execution.escalation_type == EscalationType.FREEZE_CHAT
                    else QAEscalationType.NOTIFY_ONLY
                )
                await get_qa_handoff_service().escalate_to_operator(
                    agent_id=resolved_agent.id,
                    user_external_id=normalized_user_external_id,
                    user_message=request.query,
                    answer=answer,
                    reason=execution.owner_handoff_reason,
                    channel=request.channel.value,
                    user_display_name=request.user_display_name,
                    escalation_type=qa_escalation_type,
                )
                handoff_applied = True
                escalation_type_applied = qa_escalation_type.value

            for event in execution.tool_events:
                await self._log_message(
                    agent_id=resolved_agent.id,
                    analytics_namespace_id=resolved_agent.bot_id or resolved_agent.id,
                    role="operator",
                    message_text=self._summarize_tool_event(event),
                    user_external_id=normalized_user_external_id,
                    user_display_name=request.user_display_name,
                    channel=request.channel.value,
                    telegram_peer_access_hash=request.telegram_peer_access_hash,
                    tool_name=event.get("tool_name"),
                    tool_args_hash=event.get("tool_args_hash"),
                    tool_status=event.get("tool_status"),
                    latency_ms=int(event.get("latency_ms") or 0),
                    crm_provider=event.get("crm_provider"),
                )

            if execution.fallback_to_text:
                await self._log_message(
                    agent_id=resolved_agent.id,
                    analytics_namespace_id=resolved_agent.bot_id or resolved_agent.id,
                    role="operator",
                    message_text=execution.fallback_reason or "fallback_to_text",
                    user_external_id=normalized_user_external_id,
                    user_display_name=request.user_display_name,
                    channel=request.channel.value,
                    telegram_peer_access_hash=request.telegram_peer_access_hash,
                    tool_name="fallback_to_text",
                    tool_args_hash=None,
                    tool_status="fallback",
                    latency_ms=0,
                    crm_provider=(
                        (template_config or {}).get("crm_provider")
                    ),
                )
            if handoff_applied:
                tool_status = (
                    "chat_frozen" if escalation_type_applied == "freeze_chat" else "operator_notified"
                )
                await self._log_message(
                    agent_id=resolved_agent.id,
                    analytics_namespace_id=resolved_agent.bot_id or resolved_agent.id,
                    role="operator",
                    message_text=execution.owner_handoff_reason or "qa_owner_handoff",
                    user_external_id=normalized_user_external_id,
                    user_display_name=request.user_display_name,
                    channel=request.channel.value,
                    telegram_peer_access_hash=request.telegram_peer_access_hash,
                    tool_name="qa_owner_handoff",
                    tool_args_hash=None,
                    tool_status=tool_status,
                    latency_ms=0,
                    crm_provider=None,
                )

            await self._log_message(
                agent_id=resolved_agent.id,
                analytics_namespace_id=resolved_agent.bot_id or resolved_agent.id,
                role="agent",
                message_text=answer,
                user_external_id=normalized_user_external_id,
                user_display_name=request.user_display_name,
                channel=request.channel.value,
                telegram_peer_access_hash=request.telegram_peer_access_hash,
            )

            return MessageResponse(text=answer, status=ProcessingStatus.SUCCESS)
        except Exception:
            logger.exception(
                "Error processing message: bot_id=%s channel=%s",
                request.bot_id,
                request.channel.value,
            )
            return MessageResponse(
                text="⚠️ Произошла ошибка при обработке вашего сообщения. Попробуйте позже.",
                status=ProcessingStatus.ERROR,
            )

    async def _resolve_agent(self, lookup_bot_id: int):
        async with async_session_maker() as session:
            async with session.begin():
                # Resolve by public channel id first to avoid ambiguous `id OR bot_id` matches.
                agent = await session.scalar(select(Agent).where(Agent.bot_id == lookup_bot_id))
                if agent is not None:
                    return agent
                if 0 < lookup_bot_id <= MAX_INT32:
                    return await session.scalar(select(Agent).where(Agent.id == lookup_bot_id))
                return None

    async def _is_subscription_valid(self, agent_id: int) -> bool:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    row = await session.execute(
                        select(User.subscription_end_date)
                        .join(Agent, Agent.user_id == User.id)
                        .where(Agent.id == agent_id)
                    )
                    subscription_end = row.scalar_one_or_none()
                    if not subscription_end:
                        return True
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    return subscription_end >= now
        except Exception:
            logger.exception("Subscription check failed for agent_id=%s", agent_id)
            return True

    async def _is_user_frozen(self, agent_id: int, user_external_id: str) -> bool:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    frozen_id = await session.scalar(
                        select(AgentFrozenUser.id).where(
                            AgentFrozenUser.agent_id == agent_id,
                            AgentFrozenUser.user_external_id == user_external_id,
                        )
                    )
                    return bool(frozen_id)
        except Exception:
            logger.warning(
                "Frozen check failed for agent_id=%s user=%s",
                agent_id,
                user_external_id,
            )
            return False

    async def _log_message(
        self,
        *,
        agent_id: int,
        analytics_namespace_id: int,
        role: str,
        message_text: str,
        user_external_id: str | None,
        user_display_name: str | None,
        channel: str,
        telegram_peer_access_hash: int | None,
        tool_name: str | None = None,
        tool_args_hash: str | None = None,
        tool_status: str | None = None,
        latency_ms: int | None = None,
        crm_provider: str | None = None,
    ) -> None:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    session.add(
                        AgentAnalyticsMessage(
                            agent_id=agent_id,
                            bot_id=analytics_namespace_id,
                            role=role,
                            channel=channel,
                            user_external_id=user_external_id,
                            user_display_name=user_display_name,
                            telegram_peer_access_hash=telegram_peer_access_hash,
                            tool_name=tool_name,
                            tool_args_hash=tool_args_hash,
                            tool_status=tool_status,
                            latency_ms=latency_ms,
                            crm_provider=crm_provider,
                            message_text=message_text,
                        )
                    )
        except Exception:
            logger.warning("Analytics logging failed for agent_id=%s role=%s", agent_id, role)


_processor: MessageProcessor | None = None


def get_message_processor() -> MessageProcessor:
    global _processor
    if _processor is None:
        _processor = MessageProcessor()
    return _processor
