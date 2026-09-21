"""Daily private dialogs between pool accounts so they do not look like comment-only bots."""
from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_should_idle
from .rotation_service import record_successful_send
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import CustomAccountPeerDialog, CustomAutomation, PoolAccount, SocialAccount
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

PEER_GAP_MIN_SECONDS = 60 * 60
PEER_GAP_MAX_SECONDS = 2 * 60 * 60
DAILY_MIN_MESSAGES = 5
DAILY_MAX_MESSAGES = 10
HISTORY_KEEP = 12

_OPENERS = (
    "Привет, как день?",
    "Слушай, ты ещё не спал?",
    "О, ты онлайн. Чем занят?",
    "Привет. Есть минутка?",
    "Хей, давно не писал. Как ты?",
    "Ну что, как оно?",
)
_FALLBACK_REPLIES = (
    "Да норм, просто завал небольшой.",
    "Понимаю. У меня так же почти каждый день.",
    "Ха, знакомо. Ладно, потом расскажешь подробнее.",
    "Ок, тогда на связи. Я пока отойду.",
    "Давай чуть позже продолжим, мне надо отойти.",
    "Согласен. Ладно, не буду тебя держать.",
    "Звучит разумно. Я тоже так делаю.",
    "Ну ладно, тогда напиши как будет время.",
)

_DIALOG_PROMPT = """Ты пишешь короткое личное сообщение в Telegram другу.
Это живой чат двух знакомых людей, не боты и не поддержка.
Правила:
- 1 предложение, максимум 2. Без списков, без ссылок, без эмодзи-спама.
- Ответь по смыслу последнему сообщению, не повторяй его и не цикли вопросы.
- Не начинай каждое сообщение с «привет».
- Не задавай вопрос, если предыдущие два сообщения уже были вопросами — просто отреагируй или закругли.
- Если в истории уже больше 4 реплик, чаще мягко завершай («ладно, потом напиши», «ок, я отойду»).
- Тема пусть будет бытовая: работа, усталость, планы, еда, погода, мелочи.

История:
{history}

Верни ТОЛЬКО JSON: {{"text": "сообщение"}}"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _moscow_tz():
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def moscow_day_key(value: datetime | None = None) -> str:
    tz = _moscow_tz()
    current = value or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc).astimezone(tz)
    return current.astimezone(tz).date().isoformat()


def peer_gap_seconds() -> int:
    return random.randint(PEER_GAP_MIN_SECONDS, PEER_GAP_MAX_SECONDS)


def peer_start_delay_seconds() -> int:
    """Stagger first messages so pairs do not all open at the same scheduler tick."""
    return random.randint(10 * 60, PEER_GAP_MAX_SECONDS)


def daily_message_target() -> int:
    return random.randint(DAILY_MIN_MESSAGES, DAILY_MAX_MESSAGES)


def ordered_pair(left_id: int, right_id: int) -> tuple[int, int]:
    low, high = sorted((int(left_id), int(right_id)))
    return low, high


def pair_accounts(accounts: list[SocialAccount], *, rng: random.Random | None = None) -> list[tuple[SocialAccount, SocialAccount]]:
    pool = list(accounts)
    mixer = rng or random
    mixer.shuffle(pool)
    pairs: list[tuple[SocialAccount, SocialAccount]] = []
    for index in range(0, len(pool) - 1, 2):
        pairs.append((pool[index], pool[index + 1]))
    return pairs


def _account_peer_key(account: SocialAccount | None) -> str | None:
    """Prefer @username. Phone is a weak fallback (often blocked by privacy)."""
    if account is None:
        return None
    username = (account.username or "").strip().lstrip("@")
    if username:
        return username
    from .telegram_account_client import normalize_telegram_phone

    phone = normalize_telegram_phone(account.phone_number)
    if phone:
        return phone
    raw = (account.phone_number or "").strip()
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 10:
        return f"+{digits}" if not raw.startswith("+") else raw
    return None


def _account_can_peer(account: SocialAccount) -> bool:
    """Peer DMs between pool accounts need a public username — phone lookup is unreliable."""
    return bool((account.username or "").strip().lstrip("@"))


def _looks_like_repeat(text: str, history: list[dict[str, Any]]) -> bool:
    blob = re.sub(r"\s+", " ", (text or "").strip().lower())
    if len(blob) < 4:
        return True
    recent = [re.sub(r"\s+", " ", str(item.get("text") or "").strip().lower()) for item in history[-4:]]
    return blob in recent


def _history_blob(history: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in history[-HISTORY_KEEP:]:
        role = "A" if item.get("side") == "low" else "B"
        lines.append(f"{role}: {item.get('text') or ''}")
    return "\n".join(lines) or "пока пусто, начни разговор коротко и по-человечески"


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"text": raw.strip().strip('"')}


async def generate_peer_text(history: list[dict[str, Any]], *, opener: bool) -> str:
    if opener and not history:
        return random.choice(_OPENERS)
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": _DIALOG_PROMPT.format(history=_history_blob(history))}],
            max_tokens=80,
            temperature=0.95,
        )
        data = _extract_json(response.choices[0].message.content or "")
        text = str(data.get("text") or "").strip()[:280]
        if text and not _looks_like_repeat(text, history):
            return text
    except Exception as exc:
        logger.warning("Peer dialog generation failed: %s", exc)
    return random.choice(_FALLBACK_REPLIES)


def _reset_dialog_if_new_day(dialog: CustomAccountPeerDialog, today: str) -> None:
    if dialog.day_key == today:
        return
    dialog.day_key = today
    dialog.messages_today = 0
    dialog.daily_target = daily_message_target()
    dialog.status = "idle"
    dialog.next_send_at = None
    dialog.next_sender_id = None


def _busy_account_ids(dialogs: list[CustomAccountPeerDialog], today: str) -> set[int]:
    busy: set[int] = set()
    for dialog in dialogs:
        if dialog.day_key != today:
            continue
        if (dialog.messages_today or 0) > 0 or dialog.status == "active":
            busy.add(dialog.account_low_id)
            busy.add(dialog.account_high_id)
    return busy


async def _load_alive_accounts(session: AsyncSession, automation_id: int) -> list[SocialAccount]:
    result = await session.execute(
        select(SocialAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.removed_at.is_(None),
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
            SocialAccount.is_spamblocked.is_(False),
            SocialAccount.session_file_path.isnot(None),
            SocialAccount.username.isnot(None),
        )
    )
    accounts = []
    seen: set[int] = set()
    for account in result.scalars().all():
        if account.id in seen or not _account_can_peer(account):
            continue
        seen.add(account.id)
        accounts.append(account)
    return accounts


async def _get_or_create_dialog(
    session: AsyncSession,
    automation_id: int,
    left: SocialAccount,
    right: SocialAccount,
) -> CustomAccountPeerDialog:
    low_id, high_id = ordered_pair(left.id, right.id)
    dialog = await session.scalar(
        select(CustomAccountPeerDialog).where(
            CustomAccountPeerDialog.custom_automation_id == automation_id,
            CustomAccountPeerDialog.account_low_id == low_id,
            CustomAccountPeerDialog.account_high_id == high_id,
        )
    )
    if dialog:
        return dialog
    now = _utc_now()
    dialog = CustomAccountPeerDialog(
        custom_automation_id=automation_id,
        account_low_id=low_id,
        account_high_id=high_id,
        status="idle",
        day_key=moscow_day_key(),
        daily_target=daily_message_target(),
        messages_today=0,
        history=[],
        created_at=now,
        updated_at=now,
    )
    session.add(dialog)
    await session.flush()
    return dialog


async def _send_peer_message(
    session: AsyncSession,
    automation: CustomAutomation,
    sender: SocialAccount,
    recipient: SocialAccount,
    text: str,
    *,
    first: bool,
) -> bool:
    peer = _account_peer_key(recipient)
    if not peer:
        return False
    try:
        async with TelegramAccountClient.for_account(sender) as client:
            await execute_with_telegram_retry(
                session,
                sender,
                lambda: client.human_reply(peer, text, skip_read=first),
                action_type="peer_dialog",
                target_id=str(recipient.id),
                target_type="account",
                payload={"text": text, "to_account_id": recipient.id, "to": peer},
                automation_id=automation.id,
            )
        record_successful_send(sender)
        return True
    except Exception as exc:
        logger.warning("Peer dialog send failed %s -> %s: %s", sender.id, recipient.id, exc)
        return False


def _other_account(dialog: CustomAccountPeerDialog, sender_id: int, by_id: dict[int, SocialAccount]) -> SocialAccount | None:
    other_id = dialog.account_high_id if sender_id == dialog.account_low_id else dialog.account_low_id
    return by_id.get(other_id)


async def _advance_dialog(
    session: AsyncSession,
    automation: CustomAutomation,
    dialog: CustomAccountPeerDialog,
    sender: SocialAccount,
    recipient: SocialAccount,
    *,
    opener: bool,
) -> bool:
    if account_should_idle(sender):
        dialog.next_send_at = _utc_now() + timedelta(minutes=12)
        dialog.updated_at = _utc_now()
        return False
    history = list(dialog.history or [])
    text = await generate_peer_text(history, opener=opener)
    ok = await _send_peer_message(session, automation, sender, recipient, text, first=opener or not history)
    if not ok:
        dialog.next_send_at = _utc_now() + timedelta(minutes=30)
        dialog.updated_at = _utc_now()
        return False
    side = "low" if sender.id == dialog.account_low_id else "high"
    history.append({"from": sender.id, "side": side, "text": text, "at": _utc_now().isoformat()})
    dialog.history = history[-HISTORY_KEEP:]
    dialog.last_text = text
    dialog.messages_today = int(dialog.messages_today or 0) + 1
    dialog.status = "active"
    dialog.day_key = moscow_day_key()
    if dialog.messages_today >= int(dialog.daily_target or DAILY_MIN_MESSAGES):
        dialog.status = "idle"
        dialog.next_sender_id = None
        dialog.next_send_at = None
    else:
        dialog.next_sender_id = recipient.id
        dialog.next_send_at = _utc_now() + timedelta(seconds=peer_gap_seconds())
    dialog.updated_at = _utc_now()
    return True


async def run_peer_dialog_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    sent = 0
    started = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "not_found"}
        accounts = await _load_alive_accounts(session, automation_id)
        if len(accounts) < 2:
            return {"status": "skipped", "reason": "need_two_accounts", "sent": 0}
        by_id = {account.id: account for account in accounts}
        today = moscow_day_key()
        rows = list(
            (
                await session.execute(
                    select(CustomAccountPeerDialog).where(
                        CustomAccountPeerDialog.custom_automation_id == automation_id
                    )
                )
            ).scalars().all()
        )
        for dialog in rows:
            _reset_dialog_if_new_day(dialog, today)

        now = _utc_now()
        for dialog in rows:
            if dialog.status != "active" or not dialog.next_send_at or dialog.next_send_at > now:
                continue
            if int(dialog.messages_today or 0) >= int(dialog.daily_target or DAILY_MIN_MESSAGES):
                dialog.status = "idle"
                dialog.next_send_at = None
                continue
            sender = by_id.get(int(dialog.next_sender_id or 0))
            if sender is None:
                dialog.status = "idle"
                continue
            recipient = _other_account(dialog, sender.id, by_id)
            if recipient is None:
                continue
            opener = int(dialog.messages_today or 0) == 0
            if await _advance_dialog(session, automation, dialog, sender, recipient, opener=opener):
                sent += 1
                if opener:
                    started += 1
            await session.commit()

        busy = _busy_account_ids(rows, today)
        free = [account for account in accounts if account.id not in busy]
        for left, right in pair_accounts(free):
            dialog = await _get_or_create_dialog(session, automation_id, left, right)
            _reset_dialog_if_new_day(dialog, today)
            if dialog.status == "active":
                continue
            if int(dialog.messages_today or 0) >= int(dialog.daily_target or DAILY_MIN_MESSAGES):
                continue
            # Schedule opener later instead of firing every free pair at once.
            dialog.status = "active"
            dialog.next_sender_id = left.id
            dialog.next_send_at = now + timedelta(seconds=peer_start_delay_seconds())
            dialog.updated_at = _utc_now()
            started += 1
            await session.commit()
    return {"status": "ok", "sent": sent, "started": started}
