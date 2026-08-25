"""Neurocommenting: pool accounts leave relevant comments on posts."""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .post_engagement import NEUROCOMMENTING, SHILLING, SKIP, claim_post_engagement
from .rotation_service import select_account_for_action
from .shilling_service import perform_post_shilling
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import AutomationActionLog, ChatJoinStatus, ChatMode, ChatTarget, CustomAutomation, CustomPrompt, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


DEFAULT_NEUROCOMMENTING_PROMPT = """Ты — участник Telegram-чата/канала. Тебе показали пост.
Напиши короткий, естественный, релевантный комментарий (1-2 предложения), который продолжает дискуссию или добавляет ценность.
Не спами, не используй хештеги, не предлагай ссылки.

Пост:
{post_text}

Контекст чата:
{chat_title}

Верни ТОЛЬКО JSON:
{
  "comment": "текст комментария"
}"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def _load_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.NEUROCOMMENTING.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_NEUROCOMMENTING_PROMPT


async def _generate_comment(
    session: AsyncSession,
    automation_id: int,
    *,
    post_text: str,
    chat_title: str,
) -> str:
    prompt = (await _load_prompt(session, automation_id)).format(
        post_text=post_text or "",
        chat_title=chat_title or "",
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.8,
        )
        data = _extract_json(response.choices[0].message.content or "")
        comment = str(data.get("comment") or "").strip()
        return comment[:500]
    except Exception as exc:
        logger.warning("Comment generation failed: %s", exc)
        return ""


async def _already_commented(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    message_id: int,
) -> bool:
    target_id = f"{chat_target_id}:{message_id}"
    count = await session.scalar(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "neurocommenting",
            AutomationActionLog.target_id == target_id,
            AutomationActionLog.result == "success",
        )
    )
    return count is not None


async def _send_comment(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    account: SocialAccount,
    post_id: int,
    text: str,
) -> bool:
    if not account.session_file_path:
        return False
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False

    try:
        async with TelegramAccountClient(str(session_path)) as client:
            entity = await client.get_entity(
                chat_target.invite_link or chat_target.external_chat_id or chat_target.title
            )
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.client.send_message(entity, text, comment_to=post_id),
                action_type="neurocommenting",
                target_id=f"{chat_target.id}:{post_id}",
                target_type="chat_post",
                payload={"chat_target_id": chat_target.id, "post_id": post_id, "text": text},
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("Send comment failed for chat %s post %s: %s", chat_target.id, post_id, exc)
        return False

    log = AutomationActionLog(
        custom_automation_id=automation_id,
        social_account_id=account.id,
        action_type="neurocommenting",
        target_id=f"{chat_target.id}:{post_id}",
        target_type="chat_post",
        result="success",
        payload={"chat_target_id": chat_target.id, "post_id": post_id, "text": text},
        created_at=_utc_now(),
    )
    session.add(log)
    await session.commit()
    return True


async def process_chat_target(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    max_comments_per_run: int = 5,
) -> dict[str, Any]:
    if chat_target.mode in {ChatMode.INACTIVE.value, ChatMode.SHILLING.value, ChatMode.DISCUSSION.value}:
        return {"status": "skipped", "reason": "mode"}
    if chat_target.join_status != ChatJoinStatus.JOINED.value:
        return {"status": "skipped", "reason": "not_joined"}

    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return {"status": "skipped", "reason": "automation_missing"}
    neuro_enabled = bool(automation.is_neurocommenting_enabled)
    shilling_enabled = bool(automation.is_shilling_enabled)
    if not neuro_enabled and not shilling_enabled:
        return {"status": "skipped", "reason": "feature_disabled"}

    config = chat_target.neurocommenting_config or {}
    max_per_day = int(config.get("max_per_day") or 10)
    frequency_minutes = int(config.get("frequency_minutes") or 60)
    last_commented_at = chat_target.last_scanned_at  # reuse as last comment time
    if last_commented_at and (_utc_now() - last_commented_at) < timedelta(minutes=frequency_minutes):
        return {"status": "skipped", "reason": "frequency"}

    scanner_action = "commenting" if neuro_enabled else "shilling"
    account = await select_account_for_action(session, automation_id, scanner_action, consume_quota=False)
    if not account:
        return {"status": "skipped", "reason": "no_account"}

    if not account.session_file_path:
        return {"status": "skipped", "reason": "no_session"}

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return {"status": "skipped", "reason": "session_missing"}

    posts = []
    try:
        async with TelegramAccountClient(str(session_path)) as client:
            entity = await client.get_entity(
                chat_target.invite_link or chat_target.external_chat_id or chat_target.title
            )
            history = await client.client.get_messages(entity, limit=30)
            for msg in history:
                if not msg or not msg.text or msg.id is None:
                    continue
                sender = getattr(msg, "sender", None)
                sender_id = getattr(sender, "id", None)
                if sender_id == account.id or (sender_id and str(sender_id) in (account.username or "")):
                    continue
                posts.append(msg)
    except Exception as exc:
        logger.warning("Fetch posts for chat %s failed: %s", chat_target.id, exc)
        return {"status": "error", "error": str(exc)}

    sent = 0
    shilled = 0
    for post in posts[:max_comments_per_run]:
        if await _already_commented(session, automation_id, chat_target.id, post.id):
            continue

        claimed = await claim_post_engagement(
            session,
            automation_id=automation_id,
            chat_target_id=chat_target.id,
            post_id=post.id,
            account_id=account.id,
            neuro_enabled=neuro_enabled,
            shilling_enabled=shilling_enabled,
        )
        if claimed == SKIP:
            continue
        if claimed == SHILLING:
            result = await perform_post_shilling(
                session,
                automation,
                chat_target,
                post.id,
                post_text=post.text or "",
            )
            if result.get("status") == "ok":
                shilled += 1
            continue
        if claimed != NEUROCOMMENTING or not neuro_enabled:
            continue
        if account.daily_messages_sent >= max_per_day:
            continue

        comment = await _generate_comment(session, automation_id, post_text=post.text, chat_title=chat_target.title or "")
        if not comment:
            continue

        success = await _send_comment(session, automation_id, chat_target, account, post.id, comment)
        if success:
            sent += 1
            account.daily_messages_sent += 1
            account.last_used_at = _utc_now()

    chat_target.last_scanned_at = _utc_now()
    chat_target.updated_at = _utc_now()
    await session.commit()
    return {"status": "ok", "sent": sent, "shilled": shilled}


async def run_neurocommenting_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    total_sent = 0
    chat_count = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not (
            automation.is_neurocommenting_enabled or automation.is_shilling_enabled
        ):
            logger.info("Post engagement disabled or automation not found for %s", automation_id)
            return {"status": "skipped", "reason": "feature_disabled", "chats_processed": 0, "comments_sent": 0}

        result = await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.is_active.is_(True),
                ChatTarget.join_status == ChatJoinStatus.JOINED.value,
                ChatTarget.mode != ChatMode.INACTIVE.value,
            )
        )
        chats = result.scalars().all()
        for chat_target in chats:
            try:
                res = await process_chat_target(session, automation_id, chat_target)
                chat_count += 1
                if res.get("sent"):
                    total_sent += int(res["sent"])
            except Exception as exc:
                logger.exception("Neurocommenting failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chat_count, "comments_sent": total_sent}
