"""Chat broadcasts: send a short text chain to groups from pool accounts."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import (
    STAGE_CAUTIOUS,
    account_humanization_stage,
    account_should_idle,
    farm_overlap_active_hours,
    moscow_now,
    schedule_account_target_rest,
)
from .module_account_filters import no_accounts_picked, skip_account_for_module
from .chat_membership_service import account_is_joined
from .chat_scope import is_group_chat, is_paused
from .conversation_guard import sanitize_public_text
from .human_dm import human_send_public
from .rotation_service import record_successful_send
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from .telegram_invite import chat_entity_key
from ...alembic.models import (
    AccountChatMembership,
    AutomationActionLog,
    ChatJoinStatus,
    ChatTarget,
    CustomAutomation,
    PoolAccount,
    SocialAccount,
)
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

ACTION = "chat_broadcast"
_SPINTAX_RE = re.compile(r"\{([^{}|]+(?:\|[^{}|]+)+)\}")

DEFAULT_BROADCAST_AI = """Напиши одно короткое естественное сообщение в Telegram-группу «{chat_title}».
Без ссылок, рекламы и хештегов. 1–2 предложения, как обычный участник.
Ориентир по тону (можно игнорировать, если пусто):
{hint}

Верни только текст сообщения."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_int_list(raw: Any) -> list[int]:
    items: list[int] = []
    seen: set[int] = set()
    for value in raw or []:
        try:
            ident = int(value)
        except (TypeError, ValueError):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ident)
    return items


def apply_spintax(text: str) -> str:
    out = text or ""
    for _ in range(8):
        nxt = _SPINTAX_RE.sub(lambda match: random.choice([part.strip() for part in match.group(1).split("|") if part.strip()] or [match.group(0)]), out)
        if nxt == out:
            break
        out = nxt
    return out


def fill_broadcast_vars(text: str, *, chat: ChatTarget, account: SocialAccount) -> str:
    username = (chat.invite_link or "").strip()
    if username.startswith("https://t.me/"):
        username = username.split("t.me/", 1)[-1].split("/")[0]
    if username.startswith("@"):
        username = username[1:]
    first = (account.display_name or account.username or "").split(" ")[0]
    mapping = {
        "{group_title}": chat.title or "",
        "{group_username}": username,
        "{my_name}": account.display_name or account.username or "",
        "{my_first_name}": first,
        "{my_username}": account.username or "",
    }
    out = text or ""
    for key, value in mapping.items():
        out = out.replace(key, value)
    return out


def normalize_broadcast_messages(raw: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for entry in raw or []:
        if isinstance(entry, str):
            text = entry.strip()
        elif isinstance(entry, dict):
            text = str(entry.get("text") or "").strip()
        else:
            continue
        if not text:
            continue
        items.append({"text": text[:2000]})
        if len(items) >= 10:
            break
    return items


def _in_work_window(cfg: dict[str, Any]) -> bool:
    if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
        return False
    now = moscow_now()
    days = [int(item) for item in (cfg.get("weekdays") or []) if str(item).isdigit() or isinstance(item, int)]
    if days and now.weekday() not in days:
        return False
    start = cfg.get("work_hour_start")
    end = cfg.get("work_hour_end")
    try:
        start_h = int(start) if start not in (None, "") else None
        end_h = int(end) if end not in (None, "") else None
    except (TypeError, ValueError):
        start_h = end_h = None
    if start_h is None or end_h is None:
        return True
    hour = now.hour
    if start_h <= end_h:
        return start_h <= hour < end_h
    return hour >= start_h or hour < end_h


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


async def _already_sent(session: AsyncSession, automation_id: int, chat_id: int) -> bool:
    row = await session.scalar(
        select(AutomationActionLog.id).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == ACTION,
            AutomationActionLog.result == "success",
            AutomationActionLog.target_id == str(chat_id),
        )
    )
    return row is not None


async def _generate_ai_line(chat_title: str, hint: str) -> str:
    prompt = DEFAULT_BROADCAST_AI.format(chat_title=chat_title or "чат", hint=(hint or "").strip() or "нейтральный дружелюбный тон")
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
            temperature=0.8,
        )
        return sanitize_public_text((response.choices[0].message.content or "").strip())[:500]
    except Exception as exc:
        logger.warning("Broadcast AI line failed: %s", exc)
        return ""


async def _send_line(
    session: AsyncSession,
    automation_id: int,
    account: SocialAccount,
    chat: ChatTarget,
    text: str,
    *,
    imitate_typing: bool,
) -> bool:
    if not account.session_file_path:
        return False
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False
    body = sanitize_public_text(text)
    if len(body) < 2:
        return False

    async def _do_send():
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(chat_entity_key(chat))
            return await human_send_public(client, entity, body, lab_mode=False)

    try:
        await execute_with_telegram_retry(
            session,
            account,
            _do_send,
            action_type=ACTION,
            target_id=str(chat.id),
            target_type="chat",
            payload={"chat_target_id": chat.id, "chat_title": chat.title, "text": body[:300]},
            automation_id=automation_id,
            pace=False,
        )
    except Exception as exc:
        logger.warning("Chat broadcast send failed chat=%s account=%s: %s", chat.id, account.id, exc)
        return False
    record_successful_send(account)
    session.add(
        AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account.id,
            action_type=ACTION,
            target_id=str(chat.id),
            target_type="chat",
            result="success",
            payload={"chat_target_id": chat.id, "chat_title": chat.title, "text": body[:300]},
            created_at=_utc_now(),
        )
    )
    await session.commit()
    from .job_service import actor_label, chat_label, clip_text, log_active

    await log_active(
        automation_id,
        "chat_broadcast",
        f"{actor_label(account)} отправил в {chat_label(chat)}: «{clip_text(body)}»",
    )
    return True


def _delay_bounds(cfg: dict[str, Any], key_min: str, key_max: str, default_min: int, default_max: int) -> tuple[float, float]:
    try:
        low = int(cfg.get(key_min) if cfg.get(key_min) is not None else default_min)
    except (TypeError, ValueError):
        low = default_min
    try:
        high = int(cfg.get(key_max) if cfg.get(key_max) is not None else default_max)
    except (TypeError, ValueError):
        high = default_max
    low = max(0, min(low, 3600))
    high = max(low, min(high, 3600))
    return float(low), float(high)


async def _eligible_accounts(session: AsyncSession, automation_id: int, cfg: dict[str, Any]) -> list[SocialAccount]:
    allowed = set(_as_int_list(cfg.get("account_ids")))
    blocked = set(_as_int_list(cfg.get("blacklisted_account_ids")))
    pairs = (
        await session.execute(
            select(SocialAccount, PoolAccount)
            .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(PoolAccount.custom_automation_id == automation_id)
        )
    ).all()
    out: list[SocialAccount] = []
    for account, _pool in pairs:
        if allowed and account.id not in allowed:
            continue
        if account.id in blocked:
            continue
        if not account.is_active or account.is_banned or account.is_frozen or account.is_spamblocked:
            continue
        if skip_account_for_module(cfg, account, _pool):
            continue
        if account_should_idle(account):
            continue
        if not account.session_file_path:
            continue
        if not (_media_root() / account.session_file_path).exists():
            continue
        out.append(account)
    return out


async def _target_chats(session: AsyncSession, automation_id: int, cfg: dict[str, Any], accounts: list[SocialAccount]) -> list[ChatTarget]:
    from .task_targets import resolve_task_chat_ids

    pool_ids = set(await resolve_task_chat_ids(session, automation_id, cfg))
    only_joined = bool(cfg.get("only_joined", True)) and not pool_ids
    stmt = select(ChatTarget).where(
        ChatTarget.custom_automation_id == automation_id,
        ChatTarget.black_boxed_at.is_(None),
    )
    if pool_ids:
        stmt = stmt.where(ChatTarget.id.in_(pool_ids))
    elif only_joined:
        if not accounts:
            return []
        joined_ids = (
            await session.execute(
                select(AccountChatMembership.chat_target_id).where(
                    AccountChatMembership.custom_automation_id == automation_id,
                    AccountChatMembership.social_account_id.in_([item.id for item in accounts]),
                    AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
                )
            )
        ).scalars().all()
        if not joined_ids:
            return []
        stmt = stmt.where(ChatTarget.id.in_(set(joined_ids)))
    else:
        return []
    chats = list((await session.execute(stmt)).scalars().all())
    return [chat for chat in chats if is_group_chat(chat) and not is_paused(chat)]


async def run_chat_broadcast_pass(automation_id: int, run_config: dict[str, Any] | None = None) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    sent = 0
    chats_ok = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "missing", "sent": 0}
        cfg = run_config if isinstance(run_config, dict) else ((automation.module_settings or {}).get("chat_broadcasts") or {})
        if not bool(cfg.get("enabled")):
            return {"status": "skipped", "reason": "disabled", "sent": 0}
        if no_accounts_picked(cfg):
            return {"status": "skipped", "reason": "no_accounts", "sent": 0}
        if not _in_work_window(cfg):
            return {"status": "skipped", "reason": "schedule", "sent": 0}
        end_at = str(cfg.get("end_at") or "").strip()
        if end_at:
            try:
                until = datetime.fromisoformat(end_at.replace("Z", ""))
                if _utc_now() >= until.replace(tzinfo=None):
                    return {"status": "skipped", "reason": "ended", "sent": 0}
            except ValueError:
                pass
        messages = normalize_broadcast_messages(cfg.get("messages"))
        first_mode = str(cfg.get("first_mode") or "template").strip().lower()
        if first_mode not in {"template", "ai"}:
            first_mode = "template"
        if first_mode == "template" and not messages:
            return {"status": "skipped", "reason": "no_messages", "sent": 0}
        accounts = await _eligible_accounts(session, automation_id, cfg)
        if not accounts:
            return {"status": "skipped", "reason": "no_accounts", "sent": 0}
        chats = await _target_chats(session, automation_id, cfg, accounts)
        skip_sent = bool(cfg.get("skip_sent"))
        skip_errors = bool(cfg.get("skip_errors", True))
        imitate = bool(cfg.get("imitate_typing", True))
        work_mode = str(cfg.get("work_mode") or "count").strip().lower()
        try:
            max_messages = int(cfg.get("max_messages") or 100)
        except (TypeError, ValueError):
            max_messages = 100
        if work_mode == "time":
            max_messages = 500
        max_messages = max(1, min(500, max_messages))
        try:
            errors_until_stop = max(1, min(50, int(cfg.get("errors_until_stop") or 10)))
        except (TypeError, ValueError):
            errors_until_stop = 10
        g_lo, g_hi = _delay_bounds(cfg, "delay_group_min", "delay_group_max", 30, 90)
        m_lo, m_hi = _delay_bounds(cfg, "delay_msg_min", "delay_msg_max", 3, 8)
        warmup_slow = 2 if bool(cfg.get("warmup_slow", True)) else 1
        consecutive_errors = 0
        rr = 0
        for chat in chats:
            if sent >= max_messages:
                break
            if skip_sent and await _already_sent(session, automation_id, chat.id):
                continue
            picked = None
            for offset in range(len(accounts)):
                candidate = accounts[(rr + offset) % len(accounts)]
                if await account_is_joined(session, chat.id, candidate.id):
                    picked = candidate
                    rr += offset + 1
                    break
            if picked is None:
                continue
            factor = warmup_slow if account_humanization_stage(picked) == STAGE_CAUTIOUS else 1
            chain = list(messages)
            if first_mode == "ai":
                hint = chain[0]["text"] if chain else ""
                generated = await _generate_ai_line(chat.title or "", hint)
                if generated:
                    chain = [{"text": generated}, *chain[1:]]
                elif not chain:
                    consecutive_errors += 1
                    if consecutive_errors >= errors_until_stop:
                        break
                    continue
            ok_chat = False
            for index, item in enumerate(chain):
                if sent >= max_messages:
                    break
                text = fill_broadcast_vars(apply_spintax(item["text"]), chat=chat, account=picked)
                success = await _send_line(
                    session, automation_id, picked, chat, text, imitate_typing=imitate
                )
                if success:
                    sent += 1
                    ok_chat = True
                    consecutive_errors = 0
                    if index < len(chain) - 1:
                        await asyncio.sleep(random.uniform(m_lo, m_hi) * factor)
                else:
                    consecutive_errors += 1
                    if not skip_errors or consecutive_errors >= errors_until_stop:
                        if bool(cfg.get("limit_rate", True)):
                            schedule_account_target_rest(picked)
                            await session.commit()
                        return {"status": "stopped", "reason": "errors", "sent": sent, "chats": chats_ok}
                    break
            if ok_chat:
                chats_ok += 1
                if bool(cfg.get("limit_rate", True)):
                    schedule_account_target_rest(picked)
                    await session.commit()
                await asyncio.sleep(random.uniform(g_lo, g_hi) * factor)
    return {"status": "ok", "sent": sent, "chats": chats_ok}
