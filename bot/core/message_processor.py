"""Unified message processing service for all channels."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import status

from core.backendAPI import APIcreate, APIread, get_response_status
from services.ai_service import get_answer

logger = logging.getLogger(__name__)


class Channel(str, Enum):
    """Supported message channels."""
    TELEGRAM = "telegram"
    TELEGRAM_USERBOT = "telegram_userbot"
    WHATSAPP_USERBOT = "whatsapp_userbot"


class ProcessingStatus(str, Enum):
    """Message processing result status."""
    SUCCESS = "success"
    BLOCKED_USER = "blocked_user"
    EXPIRED_SUBSCRIPTION = "expired_subscription"
    WELCOME = "welcome"
    ERROR = "error"


@dataclass
class MessageRequest:
    """Unified message request from any channel."""
    bot_id: int
    query: str
    user_external_id: str
    channel: Channel
    system_prompt: str = ""
    welcome_message: str | None = None
    user_display_name: str | None = None
    telegram_peer_access_hash: int | None = None


@dataclass
class MessageResponse:
    """Unified message response."""
    text: str
    status: ProcessingStatus


class MessageProcessor:
    """
    Unified message processor for all channels.
    
    This service:
    - Checks subscription status
    - Checks if user is frozen
    - Handles /start command
    - Logs analytics
    - Retrieves context from knowledge base
    - Generates LLM response
    - Logs response analytics
    """

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger

    async def process(self, request: MessageRequest) -> MessageResponse:
        """
        Process incoming message from any channel.
        
        Returns MessageResponse with status and text.
        """
        try:
            # 1. Subscription check
            subscription_check = await self._check_subscription(request.bot_id)
            if not subscription_check.get("valid"):
                return MessageResponse(
                    text=(
                        "⚠️ Извините, но этот бот временно недоступен.\n"
                        "Владельцу бота необходимо проверить статус своей подписки."
                    ),
                    status=ProcessingStatus.EXPIRED_SUBSCRIPTION,
                )

            # 2. User frozen check
            frozen_check = await self._check_user_frozen(request.bot_id, request.user_external_id)
            if frozen_check.get("frozen"):
                msg = (
                    "Доступ к этому агенту для вас временно ограничен владельцем. "
                    "Если это ошибка, обратитесь в поддержку."
                )
                return MessageResponse(
                    text=msg,
                    status=ProcessingStatus.BLOCKED_USER,
                )

            # 3. /start command handling
            if request.query.strip() == "/start":
                welcome_text = request.welcome_message or "Здравствуйте! Чем я могу вам помочь?"
                return MessageResponse(
                    text=welcome_text,
                    status=ProcessingStatus.WELCOME,
                )

            # 4. Log incoming user message
            await self._log_message(
                bot_id=request.bot_id,
                role="user",
                message_text=request.query,
                user_external_id=request.user_external_id,
                user_display_name=request.user_display_name,
                channel=request.channel,
                telegram_peer_access_hash=request.telegram_peer_access_hash,
            )

            # 5. Retrieve context from knowledge base
            context = await self._get_context(request.bot_id, request.query)
            context_list = context if isinstance(context, list) else []

            # 6. Generate LLM response
            answer = await self._generate_answer(
                query=request.query,
                context=context_list,
                system_prompt=request.system_prompt,
            )

            # 7. Log outgoing agent response
            await self._log_message(
                bot_id=request.bot_id,
                role="agent",
                message_text=answer,
                user_external_id=request.user_external_id,
                user_display_name=request.user_display_name,
                channel=request.channel,
                telegram_peer_access_hash=request.telegram_peer_access_hash,
            )

            return MessageResponse(text=answer, status=ProcessingStatus.SUCCESS)

        except Exception as exc:
            self.logger.exception(
                "Error processing message: bot_id=%s, channel=%s",
                request.bot_id,
                request.channel,
            )
            return MessageResponse(
                text="⚠️ Произошла ошибка при обработке вашего сообщения. Попробуйте позже.",
                status=ProcessingStatus.ERROR,
            )

    async def _check_subscription(self, bot_id: int) -> dict[str, Any]:
        """
        Check if agent owner's subscription is valid.
        
        Returns dict with 'valid' key (bool).
        """
        try:
            owner_json = await APIread.userBy_agentID(bot_id)
            if owner_json.get("error_code"):
                self.logger.warning("Failed to fetch owner for bot_id=%s", bot_id)
                # Assume subscription valid on backend error (fail open)
                return {"valid": True}

            subscription_end_raw = owner_json.get("subscription_end_date")
            if not subscription_end_raw:
                # No expiry date = valid subscription (e.g., Free tier)
                return {"valid": True}

            try:
                subscription_end = datetime.fromisoformat(subscription_end_raw)
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                is_valid = subscription_end >= now
                return {"valid": is_valid}
            except (ValueError, TypeError) as exc:
                self.logger.warning(
                    "Failed to parse subscription_end_date=%s: %s",
                    subscription_end_raw,
                    exc,
                )
                # Assume valid on parse error (fail open)
                return {"valid": True}

        except Exception as exc:
            self.logger.exception("Subscription check failed for bot_id=%s", bot_id)
            # Fail open: assume subscription valid if check fails
            return {"valid": True}

    async def _check_user_frozen(self, bot_id: int, user_external_id: str) -> dict[str, Any]:
        """
        Check if user is frozen/blocked for this agent.
        
        Returns dict with 'frozen' key (bool).
        """
        try:
            frozen_check = await APIread.agentFrozenCheck(bot_id, user_external_id)
            if get_response_status(frozen_check) == status.HTTP_200_OK:
                return {"frozen": frozen_check.get("frozen", False)}
            return {"frozen": False}
        except Exception as exc:
            self.logger.warning(
                "Frozen check failed for bot_id=%s, user=%s: %s",
                bot_id,
                user_external_id,
                exc,
            )
            # Fail open: assume user not frozen if check fails
            return {"frozen": False}

    async def _log_message(
        self,
        bot_id: int,
        role: str,
        message_text: str,
        user_external_id: str,
        user_display_name: str | None,
        channel: Channel,
        telegram_peer_access_hash: int | None = None,
    ) -> None:
        """Log message to analytics."""
        try:
            await APIcreate.logAgentAnalyticsMessage(
                bot_id=bot_id,
                role=role,
                message_text=message_text,
                user_external_id=user_external_id,
                user_display_name=user_display_name,
                channel=channel.value,
                telegram_peer_access_hash=telegram_peer_access_hash,
            )
        except Exception as exc:
            # Log analytics failures but don't break message flow
            self.logger.warning(
                "Analytics logging failed: bot_id=%s, role=%s: %s",
                bot_id,
                role,
                exc,
            )

    async def _get_context(self, bot_id: int, query: str) -> list[Any]:
        """Retrieve context from knowledge base."""
        try:
            context = await APIread.contextBy_botID(bot_id, query)
            get_response_status(context)
            if isinstance(context, dict) and context.get("error_code"):
                self.logger.warning(
                    "Context retrieval failed: bot_id=%s, error_code=%s",
                    bot_id,
                    context.get("error_code"),
                )
                return []
            return context if isinstance(context, list) else []
        except Exception as exc:
            self.logger.exception("Context retrieval failed for bot_id=%s", bot_id)
            return []

    async def _generate_answer(
        self,
        query: str,
        context: list[Any],
        system_prompt: str,
    ) -> str:
        """Generate answer using LLM."""
        try:
            return await get_answer(query, context, system_prompt)
        except Exception as exc:
            self.logger.exception("LLM generation failed")
            raise


# Global instance
_processor: MessageProcessor | None = None


def get_message_processor() -> MessageProcessor:
    """Get or create global message processor instance."""
    global _processor
    if _processor is None:
        _processor = MessageProcessor()
    return _processor
