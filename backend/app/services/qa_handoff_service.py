"""Owner handoff automation for QA template conversations."""
from __future__ import annotations

import logging

import httpx
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentFrozenUser, User
from ..config import settings

logger = logging.getLogger(__name__)


class QAHandoffService:
    async def freeze_chat_and_notify_owner(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        user_message: str,
        answer: str,
        reason: str | None,
        channel: str,
        user_display_name: str | None = None,
    ) -> None:
        normalized_uid = (user_external_id or "").strip()
        if not normalized_uid:
            return

        await self._freeze_user(agent_id=agent_id, user_external_id=normalized_uid)
        await self._send_owner_email(
            agent_id=agent_id,
            user_external_id=normalized_uid,
            user_display_name=user_display_name,
            user_message=user_message,
            answer=answer,
            reason=reason,
            channel=channel,
        )

    async def _freeze_user(self, *, agent_id: int, user_external_id: str) -> None:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    existing = await session.scalar(
                        select(AgentFrozenUser.id).where(
                            AgentFrozenUser.agent_id == agent_id,
                            AgentFrozenUser.user_external_id == user_external_id,
                        )
                    )
                    if existing:
                        return
                    session.add(
                        AgentFrozenUser(
                            agent_id=agent_id,
                            user_external_id=user_external_id,
                        )
                    )
        except Exception:
            logger.exception("Failed to freeze QA chat: agent_id=%s user=%s", agent_id, user_external_id)

    async def _send_owner_email(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        user_display_name: str | None,
        user_message: str,
        answer: str,
        reason: str | None,
        channel: str,
    ) -> None:
        owner_email = ""
        owner_name = ""
        bot_label = f"agent#{agent_id}"
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    row = (
                        (
                            await session.execute(
                                select(
                                    User.email,
                                    User.name,
                                    Agent.bot_username,
                                )
                                .join(Agent, Agent.user_id == User.id)
                                .where(Agent.id == agent_id)
                                .limit(1)
                            )
                        )
                        .mappings()
                        .first()
                    )
            if not row:
                return
            owner_email = str(row.get("email") or "").strip().lower()
            owner_name = str(row.get("name") or "").strip()
            bot_username = str(row.get("bot_username") or "").strip()
            if bot_username:
                bot_label = f"@{bot_username}"
            if not owner_email:
                return
        except Exception:
            logger.exception("Failed to resolve owner email for agent_id=%s", agent_id)
            return

        api_token = settings.MAILOPOST_API_TOKEN.strip()
        from_email = settings.MAILOPOST_FROM_EMAIL.strip()
        base_url = settings.MAILOPOST_API_URL.strip().rstrip("/")
        if not api_token or not from_email:
            logger.warning("Mail sender is not configured for QA handoff notifications")
            return

        safe_reason = (reason or "Нет четкого ответа или нужен человек.").strip()
        safe_user_name = (user_display_name or "").strip() or "не указано"
        safe_user_message = (user_message or "").strip()[:3000]
        safe_answer = (answer or "").strip()[:3000]
        safe_channel = (channel or "").strip() or "unknown"
        subject = f"RSD: требуется вмешательство владельца ({bot_label})"
        text = (
            f"Здравствуйте, {owner_name or 'владелец агента'}.\n\n"
            "QA-бот автоматически перевел чат в заморозку и запрашивает ваше вмешательство.\n\n"
            f"Агент: {bot_label} (id={agent_id})\n"
            f"Канал: {safe_channel}\n"
            f"Пользователь: {user_external_id}\n"
            f"Имя пользователя: {safe_user_name}\n"
            f"Причина: {safe_reason}\n\n"
            f"Сообщение пользователя:\n{safe_user_message}\n\n"
            f"Ответ агента:\n{safe_answer}\n"
        )
        payload = {
            "from_email": from_email,
            "to": owner_email,
            "subject": subject,
            "text": text,
        }
        from_name = settings.MAILOPOST_FROM_NAME.strip()
        if from_name:
            payload["from_name"] = from_name

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        url = f"{base_url}/email/messages"

        timeout = httpx.Timeout(settings.MAILOPOST_SEND_TIMEOUT_SECONDS, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
            if not response.is_success:
                logger.error(
                    "QA handoff email send failed: status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
        except Exception:
            logger.exception("Failed to send QA handoff owner email for agent_id=%s", agent_id)


_qa_handoff_service: QAHandoffService | None = None


def get_qa_handoff_service() -> QAHandoffService:
    global _qa_handoff_service
    if _qa_handoff_service is None:
        _qa_handoff_service = QAHandoffService()
    return _qa_handoff_service
