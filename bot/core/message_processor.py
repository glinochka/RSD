"""Unified message processing service for all channels."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from core.backendAPI import APIcreate

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
    DISCARDED = "discarded"


@dataclass
class MessageRequest:
    """Unified message request from any channel."""
    bot_id: int
    query: str
    user_external_id: str
    channel: Channel
    system_prompt: str = ""
    welcome_message: str | None = None
    process_start_with_llm: bool = False
    user_display_name: str | None = None
    telegram_peer_access_hash: int | None = None
    voice_base64: str | None = None
    voice_mime_type: str | None = None


@dataclass
class MessageResponse:
    """Unified message response."""
    text: str
    status: ProcessingStatus


class MessageProcessor:
    """
    Unified message processor for all channels.
    
    This service forwards agent messages to backend runtime.
    """

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger

    async def process(self, request: MessageRequest) -> MessageResponse:
        """
        Process incoming message from any channel.
        
        Returns MessageResponse with status and text.
        """
        try:
            payload = await APIcreate.processAgentMessage(
                bot_id=request.bot_id,
                query=request.query,
                user_external_id=request.user_external_id,
                channel=request.channel.value,
                system_prompt=request.system_prompt,
                welcome_message=request.welcome_message,
                process_start_with_llm=request.process_start_with_llm,
                user_display_name=request.user_display_name,
                telegram_peer_access_hash=request.telegram_peer_access_hash,
                voice_base64=request.voice_base64,
                voice_mime_type=request.voice_mime_type,
            )
            if payload.get("error_code"):
                self.logger.error(
                    "Backend process_message failed: bot_id=%s channel=%s status=%s detail=%s",
                    request.bot_id,
                    request.channel.value,
                    payload.get("error_code"),
                    payload.get("error_detail"),
                )
                return MessageResponse(
                    text="⚠️ Произошла ошибка при обработке вашего сообщения. Попробуйте позже.",
                    status=ProcessingStatus.ERROR,
                )

            answer = str(payload.get("text") or "").strip()
            status_raw = str(payload.get("status") or "").strip().lower()
            try:
                response_status = ProcessingStatus(status_raw)
            except ValueError:
                response_status = ProcessingStatus.ERROR

            if response_status == ProcessingStatus.DISCARDED:
                return MessageResponse(text="", status=response_status)

            if not answer:
                answer = "⚠️ Произошла ошибка при обработке вашего сообщения. Попробуйте позже."

            return MessageResponse(text=answer, status=response_status)

        except Exception:
            self.logger.exception(
                "Error processing message: bot_id=%s, channel=%s",
                request.bot_id,
                request.channel,
            )
            return MessageResponse(
                text="⚠️ Произошла ошибка при обработке вашего сообщения. Попробуйте позже.",
                status=ProcessingStatus.ERROR,
            )

# Global instance
_processor: MessageProcessor | None = None


def get_message_processor() -> MessageProcessor:
    """Get or create global message processor instance."""
    global _processor
    if _processor is None:
        _processor = MessageProcessor()
    return _processor
