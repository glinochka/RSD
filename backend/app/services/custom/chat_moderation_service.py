"""Probe whether sent comments/shills survive moderation.

Schedule: 5–24 hours after a successful target action, the same account that
posted reads the specific message by id.  If it is gone, moderation is recorded.

State machine per chat:
  untested  →  no_moderation  after 3 kept messages
  untested  →  moderated     after 3 removed messages

Moderated chats are black-boxed: target actions stop, membership slots are
freed, and the chat is replaced in account pools with a fresh free chat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_membership_service import release_memberships_for_chat, retire_reader_and_replace
from .chat_scope import TARGET_ACTIONS
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import is_chat_read_lost
from .telegram_invite import chat_entity_key
from ...alembic.database import async_session_maker
from ...alembic.models import AutomationActionLog, ChatTarget, SocialAccount

logger = logging.getLogger(__name__)

PROBE_MIN_HOURS = 5
PROBE_MAX_HOURS = 24
PROBE_LOOKBACK_HOURS = 48


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _stable_probe_due_at(action_id: int, created_at: datetime) -> datetime:
    """Deterministic 5–24 h delay so the scheduler does not re-roll every tick."""
    span = (PROBE_MAX_HOURS - PROBE_MIN_HOURS) * 3600
    offset = PROBE_MIN_HOURS * 3600 + (int(action_id) * 1_103_515_245 % max(1, int(span)))
    return created_at + timedelta(seconds=offset)


def _message_ids_from_log(log: AutomationActionLog) -> list[int]:
    payload = log.payload or {}
    message_ids: list[int] = []
    for key in ("setup_message_id", "reply_message_id"):
        val = payload.get(key)
        if val:
            try:
                message_ids.append(int(val))
            except (TypeError, ValueError):
                pass
    if log.target_type == "chat_post" and not message_ids:
        try:
            message_ids.append(int(str(log.target_id).rsplit(":", 1)[-1]))
        except (TypeError, ValueError):
            pass
    return message_ids


async def _fetch_messages_by_id(
    client: TelegramAccountClient,
    chat_target: ChatTarget,
    message_ids: list[int],
) -> list[Any]:
    entity = await client.get_entity(chat_entity_key(chat_target))
    fetched = await client.client.get_messages(entity, ids=message_ids)
    if fetched is None:
        return []
    if not isinstance(fetched, list):
        fetched = [fetched]
    return [msg for msg in fetched if msg is not None]


async def _probe_action(
    session: AsyncSession,
    log: AutomationActionLog,
) -> bool | None:
    """Return True if message still exists, False if removed, None on error."""
    payload = log.payload or {}
    chat_id = payload.get("chat_target_id")
    if not chat_id:
        try:
            chat_id = int(str(log.target_id).split(":", 1)[0])
        except (TypeError, ValueError):
            return None
    chat_target = await session.get(ChatTarget, int(chat_id))
    if not chat_target:
        return None
    account = await session.get(SocialAccount, log.social_account_id)
    if not account or not (account.session_file_path or getattr(account, "encrypted_session", None)):
        return None

    message_ids = _message_ids_from_log(log)
    if not message_ids:
        return None

    try:
        async with TelegramAccountClient.for_account(account) as client:
            messages = await _fetch_messages_by_id(client, chat_target, message_ids)
            return any(getattr(msg, "id", None) in message_ids for msg in messages)
    except Exception as exc:
        if is_chat_read_lost(exc):
            await retire_reader_and_replace(session, chat_target, account.id, error=str(exc)[:255])
        logger.warning("Moderation probe failed for log %s: %s", log.id, exc)
        return None


def _update_mod_status(chat_target: ChatTarget, survived: bool) -> None:
    now = _utc_now()
    chat_target.mod_checked_at = now
    chat_target.updated_at = now
    if survived:
        chat_target.mod_consecutive_kept = (chat_target.mod_consecutive_kept or 0) + 1
        chat_target.mod_consecutive_removed = 0
    else:
        chat_target.mod_consecutive_removed = (chat_target.mod_consecutive_removed or 0) + 1
        chat_target.mod_consecutive_kept = 0

    if chat_target.mod_consecutive_kept >= 3:
        chat_target.mod_status = "no_moderation"
    elif chat_target.mod_consecutive_removed >= 3:
        chat_target.mod_status = "moderated"
        chat_target.black_boxed_at = now


async def run_moderation_probe_pass(automation_id: int) -> dict[str, Any]:
    """Scheduler entry: probe a small batch of recent target actions."""
    probed = 0
    moderated = 0
    no_moderation = 0
    errors = 0
    async with async_session_maker() as session:
        cutoff = _utc_now() - timedelta(hours=PROBE_LOOKBACK_HOURS)
        probed_flag = AutomationActionLog.payload["_mod_probed"].as_boolean()
        result = await session.execute(
            select(AutomationActionLog)
            .where(
                AutomationActionLog.custom_automation_id == automation_id,
                AutomationActionLog.action_type.in_(TARGET_ACTIONS),
                AutomationActionLog.result == "success",
                AutomationActionLog.created_at >= cutoff,
                or_(
                    AutomationActionLog.payload.is_(None),
                    probed_flag.is_(None),
                    probed_flag.is_(False),
                ),
            )
            .order_by(AutomationActionLog.created_at.asc())
            .limit(40)
        )
        logs = list(result.scalars().all())
        now = _utc_now()
        for log in logs:
            payload = dict(log.payload or {})
            if payload.get("_mod_probed") is True:
                continue
            created = _naive_utc(log.created_at)
            if created is None:
                continue
            due_raw = payload.get("_mod_due_at")
            if due_raw:
                try:
                    due_at = _naive_utc(datetime.fromisoformat(str(due_raw))) or _stable_probe_due_at(log.id, created)
                except ValueError:
                    due_at = _stable_probe_due_at(log.id, created)
            else:
                due_at = _stable_probe_due_at(log.id, created)
                payload["_mod_due_at"] = due_at.isoformat()
                log.payload = payload
                log.updated_at = now
            if now < due_at:
                continue
            probed += 1
            survived = await _probe_action(session, log)
            payload["_mod_probed"] = True
            payload["_mod_probed_at"] = now.isoformat()
            payload["_mod_survived"] = survived
            log.payload = payload
            log.updated_at = now

            chat_id = payload.get("chat_target_id")
            if not chat_id:
                try:
                    chat_id = int(str(log.target_id).split(":", 1)[0])
                except (TypeError, ValueError):
                    chat_id = None
            if survived is True:
                if chat_id:
                    chat_target = await session.get(ChatTarget, int(chat_id))
                    if chat_target:
                        _update_mod_status(chat_target, survived=True)
                no_moderation += 1
            elif survived is False:
                if chat_id:
                    chat_target = await session.get(ChatTarget, int(chat_id))
                    if chat_target:
                        _update_mod_status(chat_target, survived=False)
                        if chat_target.mod_status == "moderated":
                            moderated += 1
                            chat_target.mode = "inactive"
                            chat_target.updated_at = now
                            await release_memberships_for_chat(
                                session,
                                chat_target,
                                reason="moderated_blackbox",
                            )
            else:
                errors += 1
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                errors += 1
    return {"probed": probed, "moderated": moderated, "no_moderation": no_moderation, "errors": errors}
