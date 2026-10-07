"""Reply to unsolicited private messages without creating leads."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_humanization_should_idle as account_should_idle, farm_overlap_active_hours
from .conversation_guard import (
    conversation_has_link,
    entity_matches_peer_keys,
    incoming_asks_for_link,
    offer_fields,
    peer_identity_keys,
    sanitize_dm_text,
)
from .human_dm import is_ready_to_reply
from .prompt_service import render_prompt
from .rotation_service import list_alive_session_accounts
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry, log_action_error
from ...alembic.models import AutomationActionLog, CustomAutomation, CustomLead, CustomPrompt, PoolAccount, PromptType, SocialAccount
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

INBOUND_DM_ACTION = "inbound_dm"
MAX_REPLIES_PER_HOUR = 10
TELEGRAM_SERVICE_USER_IDS = {777000, 42777, 333000}
TELEGRAM_SERVICE_USERNAMES = {"telegram", "telegramnotifications"}

DEFAULT_INBOUND_DM_PROMPT = """Тебе написали в личку. Ты живой человек, не отдел продаж и не бот.

Правила:
- 1–3 коротких предложения, разговорно.
- На «привет / как дела / давно не писал» отвечай как другу. Не предлагай продукт, ссылку и промокод.
- Продукт упоминай только если собеседник сам спросил про задачу/сервис.
- Ссылку и промокод вставляй ТОЛЬКО если они явно попросили («скинь ссылку», «дай промокод») и поля ниже не пустые. Иначе не выдумывай и не вставляй URL.
- Не повторяй одно и то же. Не пиши списки фич.

Входящее сообщение:
{incoming}

Контекст продукта (не рекламируй сам):
{product_context}

Ссылка (только если попросили): {partner_utm_url}
Промокод (только если попросили): {partner_promo_code}

Верни ТОЛЬКО текст ответа без кавычек и пояснений.
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_official_telegram_peer(entity: Any) -> bool:
    peer_id = int(getattr(entity, "id", 0) or 0)
    if peer_id in TELEGRAM_SERVICE_USER_IDS:
        return True
    username = (getattr(entity, "username", None) or "").strip().lstrip("@").lower()
    return username in TELEGRAM_SERVICE_USERNAMES


def _product_context(automation: CustomAutomation) -> str:
    parts = [
        automation.name or "",
        automation.description or "",
        automation.industry or "",
    ]
    return "\n".join(part.strip() for part in parts if part and str(part).strip())


async def _load_pool_peer_keys(session: AsyncSession, automation_id: int) -> set[str]:
    rows = await session.execute(
        select(SocialAccount.username, SocialAccount.display_name).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.removed_at.is_(None),
        )
    )
    keys: set[str] = set()
    for username, display_name in rows.all():
        keys.update(peer_identity_keys(username=username, display_name=display_name))
    return keys


async def _load_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.INBOUND_DM.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_INBOUND_DM_PROMPT


async def _already_handled(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    external_message_id: str,
) -> bool:
    existing = await session.scalar(
        select(AutomationActionLog.id).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type == INBOUND_DM_ACTION,
            AutomationActionLog.target_id == external_message_id,
            AutomationActionLog.result == "success",
        ).limit(1)
    )
    return existing is not None


async def _lead_exists_for_peer(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    peer_id: int,
    username: str | None,
) -> bool:
    contacts: set[str] = {str(peer_id)}
    if username:
        clean = username.lstrip("@").lower()
        contacts.add(clean)
        contacts.add(f"@{clean}")
    rows = await session.execute(
        select(CustomLead.contact_value).where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.assigned_account_id == account_id,
            CustomLead.status.notin_(["lost", "spam"]),
        )
    )
    for (contact_value,) in rows.all():
        normalized = (contact_value or "").strip().lower()
        if normalized in contacts:
            return True
    return False


async def _hourly_reply_count(session: AsyncSession, automation_id: int, account_id: int) -> int:
    since = _utc_now() - timedelta(hours=1)
    return int(
        await session.scalar(
            select(func.count(AutomationActionLog.id)).where(
                AutomationActionLog.custom_automation_id == automation_id,
                AutomationActionLog.social_account_id == account_id,
                AutomationActionLog.action_type == INBOUND_DM_ACTION,
                AutomationActionLog.result == "success",
                AutomationActionLog.created_at >= since,
            )
        )
        or 0
    )


async def _generate_reply(
    session: AsyncSession,
    automation: CustomAutomation,
    incoming: str,
    *,
    allow_link: bool,
) -> str:
    template = await _load_prompt(session, automation.id)
    url, promo = offer_fields(
        url=automation.partner_utm_url,
        promo=automation.partner_promo_code,
        allow_link=allow_link,
    )
    prompt = render_prompt(
        template,
        {
            "incoming": incoming,
            "product_context": _product_context(automation),
            "partner_utm_url": url,
            "partner_promo_code": promo,
        },
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    text = (response.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return sanitize_dm_text(text, allow_link=allow_link)[:2000]


async def _process_account(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    *,
    pool_peer_keys: set[str],
) -> dict[str, Any]:
    if not account.session_file_path or not account.is_active or account.is_banned or getattr(account, "is_frozen", False):
        return {"status": "skipped", "reason": "inactive"}
    if account_should_idle(account):
        return {"status": "skipped", "reason": "resting"}
    if await _hourly_reply_count(session, automation.id, account.id) >= MAX_REPLIES_PER_HOUR:
        return {"status": "skipped", "reason": "hourly_limit"}

    async def _run_with_client(client: TelegramAccountClient) -> dict[str, Any]:
        handled = 0
        dialogs = await client.get_dialogs(limit=random.randint(8, 16))
        for dialog in dialogs or []:
            if not getattr(dialog, "is_user", False):
                continue
            entity = dialog.entity
            if entity is None or getattr(entity, "bot", False):
                continue
            if is_official_telegram_peer(entity):
                continue
            if entity_matches_peer_keys(entity, pool_peer_keys):
                continue
            peer_id = int(getattr(entity, "id", 0) or 0)
            username = getattr(entity, "username", None)
            if await _lead_exists_for_peer(session, automation.id, account.id, peer_id, username):
                continue
            messages = await client.get_messages(entity, limit=8)
            history_texts = [str(getattr(item, "text", "") or "") for item in (messages or [])]
            already_shared_link = conversation_has_link(history_texts)
            for msg in reversed(list(messages or [])):
                if not msg or not getattr(msg, "text", None) or getattr(msg, "out", False):
                    continue
                incoming = str(msg.text).strip()
                if not incoming:
                    continue
                external_id = f"{peer_id}:{msg.id}"
                if await _already_handled(session, automation.id, account.id, external_id):
                    continue
                if not is_ready_to_reply(msg, external_id, lab_mode=False):
                    continue
                allow_link = incoming_asks_for_link(incoming) and not already_shared_link
                try:
                    reply = await _generate_reply(
                        session, automation, incoming, allow_link=allow_link
                    )
                except Exception as exc:
                    await log_action_error(
                        session,
                        account,
                        action_type=INBOUND_DM_ACTION,
                        target_id=external_id,
                        target_type="dm",
                        error_message=str(exc)[:2000],
                        payload={"incoming": incoming[:500], "peer_id": peer_id},
                        automation_id=automation.id,
                    )
                    await session.commit()
                    continue
                if not reply:
                    continue

                async def _send_human_reply(
                    _entity=entity,
                    _msg=msg,
                    _reply=reply,
                ):
                    await client.human_reply(
                        _entity,
                        _reply,
                        incoming_message=_msg,
                        lab_mode=False,
                    )

                await execute_with_telegram_retry(
                    session,
                    account,
                    _send_human_reply,
                    action_type=INBOUND_DM_ACTION,
                    target_id=external_id,
                    target_type="dm",
                    payload={
                        "incoming": incoming[:500],
                        "reply": reply[:500],
                        "peer_id": peer_id,
                        "username": username,
                    },
                    automation_id=automation.id,
                )
                session.add(
                    AutomationActionLog(
                        custom_automation_id=automation.id,
                        social_account_id=account.id,
                        action_type=INBOUND_DM_ACTION,
                        target_id=external_id,
                        target_type="dm",
                        result="success",
                        payload={
                            "incoming": incoming[:500],
                            "reply": reply[:500],
                            "peer_id": peer_id,
                        },
                        created_at=_utc_now(),
                    )
                )
                await session.commit()
                handled += 1
                if allow_link:
                    already_shared_link = True
                if account_should_idle(account) or await _hourly_reply_count(session, automation.id, account.id) >= MAX_REPLIES_PER_HOUR:
                    return {"status": "ok", "handled": handled}
        return {"status": "ok", "handled": handled}

    try:
        try:
            async with TelegramAccountClient.for_account(account) as client:
                return await _run_with_client(client)
        except Exception as exc:
            from .proxy_service import recover_dead_proxy
            from .telegram_error_handler import looks_like_proxy_dead

            if not looks_like_proxy_dead(exc):
                raise
            rotated = await recover_dead_proxy(session, account)
            if rotated is None:
                raise
            await session.commit()
            await session.refresh(account)
            await asyncio.sleep(2)
            async with TelegramAccountClient.for_account(account) as client:
                return await _run_with_client(client)
    except Exception as exc:
        logger.warning("Inbound DM pass failed for account %s: %s", account.id, exc)
        await log_action_error(
            session,
            account,
            action_type=INBOUND_DM_ACTION,
            target_id=f"account:{account.id}",
            target_type="account",
            error_message=str(exc)[:2000],
            payload={},
            automation_id=automation.id,
        )
        await session.commit()
        return {"status": "error", "reason": str(exc)[:200]}


async def run_inbound_dm_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or automation.status == "archived":
            return {"status": "skipped", "reason": "not_found"}
        if not farm_overlap_active_hours():
            return {"status": "skipped", "reason": "night"}
        accounts = await list_alive_session_accounts(session, automation_id)
        pool_peer_keys = await _load_pool_peer_keys(session, automation_id)
        total_handled = 0
        for account in accounts:
            outcome = await _process_account(
                session, automation, account, pool_peer_keys=pool_peer_keys
            )
            total_handled += int(outcome.get("handled") or 0)
        return {"status": "ok", "handled": total_handled, "accounts": len(accounts)}
