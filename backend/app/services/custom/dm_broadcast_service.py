"""DM broadcasts: send a short text chain to users from pool accounts."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import (
    STAGE_CAUTIOUS,
    account_humanization_stage,
    account_should_idle,
    farm_overlap_active_hours,
)
from .module_account_filters import no_accounts_picked, skip_account_for_module
from .chat_broadcast_service import apply_spintax, normalize_broadcast_messages
from .conversation_guard import sanitize_public_text
from .dm_broadcast_module_service import ACTION, normalize_dm_recipients, normalize_dm_settings
from .human_dm import human_send_reply
from .humanization_session import inspect_peer_profile
from .rotation_service import record_successful_send
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import AutomationActionLog, CustomAutomation, PoolAccount, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

DEFAULT_DM_AI = """Напиши одно короткое естественное личное сообщение человеку в Telegram.
Без ссылок, рекламы и хештегов. 1–2 предложения, как знакомый.
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


def fill_dm_vars(text: str, *, recipient: str, account: SocialAccount) -> str:
    first = (account.display_name or account.username or "").split(" ")[0]
    mapping = {
        "{username}": recipient.lstrip("@"),
        "{peer}": recipient,
        "{my_name}": account.display_name or account.username or "",
        "{my_first_name}": first,
        "{my_username}": account.username or "",
    }
    out = text or ""
    for key, value in mapping.items():
        out = out.replace(key, value)
    return out


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


async def _already_sent(session: AsyncSession, automation_id: int, recipient: str) -> bool:
    row = await session.scalar(
        select(AutomationActionLog.id).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == ACTION,
            AutomationActionLog.result == "success",
            AutomationActionLog.target_id == recipient,
        )
    )
    return row is not None


async def _generate_ai_line(hint: str) -> str:
    prompt = DEFAULT_DM_AI.format(hint=(hint or "").strip() or "нейтральный дружелюбный тон")
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
            temperature=0.8,
        )
        return sanitize_public_text((response.choices[0].message.content or "").strip())[:500]
    except Exception as exc:
        logger.warning("DM broadcast AI line failed: %s", exc)
        return ""


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


def _recipient_entity_key(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("https://t.me/"):
        text = text.split("t.me/", 1)[-1].split("/")[0]
    if text.startswith("@"):
        return text[1:]
    return text


async def _send_line(
    session: AsyncSession,
    automation_id: int,
    account: SocialAccount,
    recipient: str,
    text: str,
) -> bool:
    if not account.session_file_path:
        return False
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False
    body = sanitize_public_text(text)
    if len(body) < 2:
        return False
    peer = _recipient_entity_key(recipient)

    async def _do_send():
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(peer)
            await inspect_peer_profile(client, entity)
            return await human_send_reply(client, entity, body, skip_read=True, lab_mode=False)

    try:
        await execute_with_telegram_retry(
            session,
            account,
            _do_send,
            action_type=ACTION,
            target_id=recipient,
            target_type="user",
            payload={"recipient": recipient, "text": body[:300]},
            automation_id=automation_id,
            pace=False,
        )
    except Exception as exc:
        logger.warning("DM broadcast send failed peer=%s account=%s: %s", recipient, account.id, exc)
        return False
    record_successful_send(account)
    session.add(
        AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account.id,
            action_type=ACTION,
            target_id=recipient,
            target_type="user",
            result="success",
            payload={"recipient": recipient, "text": body[:300]},
            created_at=_utc_now(),
        )
    )
    await session.commit()
    from .job_service import actor_label, clip_text, log_active

    await log_active(
        automation_id,
        "dm_broadcast",
        f"{actor_label(account)} написал {recipient}: «{clip_text(body)}»",
    )
    return True


async def run_dm_broadcast_pass(automation_id: int, run_config: dict[str, Any] | None = None) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    sent = 0
    peers_ok = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "missing", "sent": 0}
        cfg = run_config if isinstance(run_config, dict) else ((automation.module_settings or {}).get("dm_broadcasts") or {})
        cfg = normalize_dm_settings(cfg)
        if not bool(cfg.get("enabled")):
            return {"status": "skipped", "reason": "disabled", "sent": 0}
        if no_accounts_picked(cfg):
            return {"status": "skipped", "reason": "no_accounts", "sent": 0}
        if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
            return {"status": "skipped", "reason": "night", "sent": 0}
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
        if first_mode == "template" and not messages:
            return {"status": "skipped", "reason": "no_messages", "sent": 0}
        accounts = await _eligible_accounts(session, automation_id, cfg)
        if not accounts:
            return {"status": "skipped", "reason": "no_accounts", "sent": 0}
        recipients = normalize_dm_recipients(cfg.get("recipients"))
        from .task_targets import resolve_user_folder_peers

        recipients = list(dict.fromkeys([*recipients, *await resolve_user_folder_peers(session, automation_id, cfg)]))
        if not recipients:
            return {"status": "skipped", "reason": "no_recipients", "sent": 0}
        skip_sent = bool(cfg.get("skip_sent"))
        skip_errors = bool(cfg.get("skip_errors", True))
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
        p_lo, p_hi = _delay_bounds(cfg, "delay_peer_min", "delay_peer_max", 30, 90)
        m_lo, m_hi = _delay_bounds(cfg, "delay_msg_min", "delay_msg_max", 3, 8)
        consecutive_errors = 0
        rr = 0
        for recipient in recipients:
            if sent >= max_messages:
                break
            if skip_sent and await _already_sent(session, automation_id, recipient):
                continue
            if not accounts:
                break
            picked = accounts[rr % len(accounts)]
            rr += 1
            if account_should_idle(picked):
                continue
            factor = 2 if account_humanization_stage(picked) == STAGE_CAUTIOUS else 1
            chain = list(messages)
            if first_mode == "ai":
                hint = chain[0]["text"] if chain else ""
                generated = await _generate_ai_line(hint)
                if generated:
                    chain = [{"text": generated}, *chain[1:]]
                elif not chain:
                    consecutive_errors += 1
                    if consecutive_errors >= errors_until_stop:
                        break
                    continue
            ok_peer = False
            for index, item in enumerate(chain):
                if sent >= max_messages:
                    break
                text = fill_dm_vars(apply_spintax(item["text"]), recipient=recipient, account=picked)
                success = await _send_line(session, automation_id, picked, recipient, text)
                if success:
                    sent += 1
                    ok_peer = True
                    consecutive_errors = 0
                    if index < len(chain) - 1:
                        await asyncio.sleep(random.uniform(m_lo, m_hi) * factor)
                else:
                    consecutive_errors += 1
                    if not skip_errors or consecutive_errors >= errors_until_stop:
                        return {"status": "stopped", "reason": "errors", "sent": sent, "peers": peers_ok}
                    break
            if ok_peer:
                peers_ok += 1
                await asyncio.sleep(random.uniform(p_lo, p_hi) * factor)
    return {"status": "ok", "sent": sent, "peers": peers_ok}
