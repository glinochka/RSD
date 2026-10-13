"""Human-readable log of every Telegram RPC an account makes."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import CustomJob, PoolAccount, SocialAccount, TelegramAccountLog

LOG_TTL = timedelta(days=3)

logger = logging.getLogger(__name__)

_SKIP_RPC = frozenset({
    "PingRequest",
    "PingDelayDisconnectRequest",
    "HttpWaitRequest",
    "GetStateRequest",
    "GetDifferenceRequest",
    "GetConfigRequest",
    "InitConnectionRequest",
    "InvokeWithLayerRequest",
})

_RPC_RU = {
    "GetHistoryRequest": "прочитал ленту",
    "GetMessagesRequest": "открыл сообщения",
    "SendMessageRequest": "отправил сообщение",
    "SendMediaRequest": "отправил медиа",
    "SendReactionRequest": "поставил реакцию",
    "SetTypingRequest": "показал «печатает»",
    "ReadHistoryRequest": "прочитал историю",
    "ReadMentionsRequest": "прочитал упоминания",
    "GetDialogsRequest": "открыл список чатов",
    "GetPeerDialogsRequest": "открыл диалоги",
    "GetParticipantsRequest": "запросил участников",
    "GetFullChannelRequest": "открыл карточку канала",
    "GetFullChatRequest": "открыл карточку чата",
    "GetFullUserRequest": "открыл профиль",
    "GetUsersRequest": "запросил профили",
    "JoinChannelRequest": "вступил в канал",
    "LeaveChannelRequest": "вышел из канала",
    "ImportChatInviteRequest": "вступил по приглашению",
    "CheckChatInviteRequest": "проверил приглашение",
    "ForwardMessagesRequest": "переслал сообщения",
    "EditMessageRequest": "изменил сообщение",
    "DeleteMessagesRequest": "удалил сообщения",
    "GetRepliesRequest": "открыл комментарии к посту",
    "GetDiscussionMessageRequest": "открыл обсуждение поста",
    "UpdateStatusRequest": "сменил статус онлайн",
    "UpdateProfileRequest": "обновил профиль",
    "UploadProfilePhotoRequest": "обновил аватар",
    "GetAuthorizationsRequest": "посмотрел активные сессии",
    "ResetAuthorizationRequest": "завершил чужую сессию",
    "GetPasswordRequest": "проверил облачный пароль",
    "UpdatePasswordSettingsRequest": "изменил облачный пароль",
    "AcceptLoginTokenRequest": "подтвердил вход по QR",
    "CheckChatlistInviteRequest": "проверил addlist-папку",
    "JoinChatlistInviteRequest": "вступил по addlist",
    "ExportChatlistInviteRequest": "собрал addlist-ссылку",
    "EditExportedInviteRequest": "обновил addlist-ссылку",
    "GetDialogFiltersRequest": "открыл папки Telegram",
    "UpdateDialogFilterRequest": "сохранил папку Telegram",
    "GetPeerSettingsRequest": "открыл настройки диалога",
    "GetNotifySettingsRequest": "проверил уведомления",
    "SetHistoryTTLRequest": "настроил автоудаление",
    "AddContactRequest": "добавил контакт",
    "ImportContactsRequest": "импортировал контакты",
    "GetContactSignupNotificationRequest": "проверил уведомления о контактах",
    "GetPinnedDialogsRequest": "открыл закреплённые чаты",
    "GetWebPagePreviewRequest": "открыл превью ссылки",
    "GetStoriesArchiveRequest": "открыл архив историй",
    "GetPeerStoriesRequest": "открыл истории",
    "ReadStoriesRequest": "просмотрел истории",
    "SendVoteRequest": "проголосовал в опросе",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clip(text: Any, limit: int = 80) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _peer_hint(request: Any) -> str:
    for attr in ("peer", "channel", "chat_id"):
        value = getattr(request, attr, None)
        if value is None:
            continue
        username = getattr(value, "username", None)
        if username:
            return f" @{username}"
        title = getattr(value, "title", None)
        if title:
            return f" «{_clip(title, 40)}»"
        channel_id = getattr(value, "channel_id", None) or getattr(value, "chat_id", None)
        if channel_id:
            return f" #{channel_id}"
    return ""


def humanize_telegram_request(request: Any) -> str | None:
    if request is None:
        return None
    inner = getattr(request, "query", None)
    if inner is not None and type(request).__name__ == "InvokeWithLayerRequest":
        return humanize_telegram_request(inner)
    name = type(request).__name__
    if name in _SKIP_RPC:
        return None
    if name == "UpdateStatusRequest":
        offline = bool(getattr(request, "offline", False))
        return "вышел в офлайн" if offline else "вошёл в онлайн"
    base = _RPC_RU.get(name)
    if not base:
        readable = name.replace("Request", "")
        readable = "".join(f" {ch.lower()}" if ch.isupper() else ch for ch in readable).strip()
        base = readable or name
    hint = _peer_hint(request)
    message = getattr(request, "message", None)
    extra = f": «{_clip(message)}»" if message else ""
    return f"{base}{hint}{extra}"


def install_telegram_rpc_logger(client: Any, *, account_id: int | None, automation_id: int | None = None) -> None:
    """Wrap Telethon MTProtoSender.send. Instance __call__ is never used."""
    if client is None:
        return
    if account_id:
        client._rsd_account_id = account_id
    if automation_id:
        client._rsd_automation_id = automation_id
    sender = getattr(client, "_sender", None)
    if sender is None or not callable(getattr(sender, "send", None)):
        return
    if getattr(sender, "_rsd_rpc_logged", False):
        return
    original = sender.send

    async def wrapped(request, *args, **kwargs):
        aid = getattr(client, "_rsd_account_id", None) or account_id
        auto = getattr(client, "_rsd_automation_id", None) or automation_id
        inner = getattr(request, "query", None) if request is not None else None
        rpc = inner if inner is not None and type(request).__name__ == "InvokeWithLayerRequest" else request
        message = humanize_telegram_request(request)
        rpc_name = type(rpc).__name__ if rpc is not None else type(request).__name__
        try:
            result = await original(request, *args, **kwargs)
        except Exception as exc:
            if message:
                schedule_telegram_log(
                    aid,
                    auto,
                    message,
                    rpc_name=rpc_name,
                    result="error",
                    error=str(exc)[:400],
                )
            raise
        if message:
            schedule_telegram_log(
                aid,
                auto,
                message,
                rpc_name=rpc_name,
                result="ok",
            )
        return result

    sender.send = wrapped
    sender._rsd_rpc_logged = True
    client._rsd_rpc_logged = True


def schedule_telegram_log(
    account_id: int | None,
    automation_id: int | None,
    message: str,
    *,
    rpc_name: str = "",
    result: str = "ok",
    error: str | None = None,
) -> None:
    if not account_id or not message:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(
        persist_telegram_log(
            int(account_id),
            automation_id,
            message,
            rpc_name=rpc_name,
            result=result,
            error=error,
        )
    )


async def persist_telegram_log(
    account_id: int,
    automation_id: int | None,
    message: str,
    *,
    rpc_name: str = "",
    result: str = "ok",
    error: str | None = None,
) -> None:
    try:
        auto_id = int(automation_id) if automation_id else await _automation_id_for_account(account_id)
        if not auto_id:
            logger.debug("Skip telegram log for account %s: no automation", account_id)
            return
        cutoff = _utc_now() - LOG_TTL
        async with async_session_maker() as session:
            session.add(
                TelegramAccountLog(
                    custom_automation_id=auto_id,
                    social_account_id=int(account_id),
                    message=message[:500],
                    rpc_name=(rpc_name or "")[:80],
                    result=(result or "ok")[:16],
                    error_message=(error or None),
                    created_at=_utc_now(),
                )
            )
            await session.execute(
                delete(TelegramAccountLog).where(
                    TelegramAccountLog.social_account_id == int(account_id),
                    TelegramAccountLog.created_at < cutoff,
                )
            )
            await session.commit()
    except Exception:
        logger.warning("Could not persist telegram log for account %s", account_id, exc_info=True)


async def _automation_id_for_account(account_id: int) -> int | None:
    try:
        async with async_session_maker() as session:
            value = await session.scalar(
                select(PoolAccount.custom_automation_id)
                .where(PoolAccount.social_account_id == account_id)
                .limit(1)
            )
            return int(value) if value else None
    except Exception:
        return None


def _parse_log_ts(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw or "").replace("Z", "")
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _account_log_needles(account: SocialAccount | None, account_id: int) -> list[str]:
    from .job_service import actor_label

    needles: list[str] = []
    if account is not None:
        label = actor_label(account)
        if label:
            needles.append(label)
        phone = str(getattr(account, "phone_number", None) or "").strip()
        if phone:
            needles.append(phone)
        name = str(getattr(account, "display_name", None) or getattr(account, "username", None) or "").strip()
        if name:
            needles.append(name.lstrip("@"))
    needles.append(f"аккаунт #{account_id}")
    return [item for item in needles if item]


async def list_account_telegram_logs(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    cutoff = _utc_now() - LOG_TTL
    cap = max(1, min(int(limit or 200), 500))
    account = await session.get(SocialAccount, account_id)
    from .job_service import actor_label

    label = actor_label(account) if account is not None else f"аккаунт #{account_id}"
    rows = (
        await session.execute(
            select(TelegramAccountLog)
            .where(
                TelegramAccountLog.social_account_id == account_id,
                TelegramAccountLog.created_at >= cutoff,
            )
            .order_by(TelegramAccountLog.id.desc())
            .limit(cap)
        )
    ).scalars().all()
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        message = row.message
        if label and message and not message.startswith(label):
            message = f"{label} {message}"
        if row.error_message:
            message = f"{message} ({row.error_message})"
        key = (str(row.created_at or ""), message)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "id": row.id,
                "message": message,
                "rpc_name": row.rpc_name,
                "result": row.result,
                "error": row.error_message,
                "created_at": row.created_at,
            }
        )
    jobs = (
        await session.execute(
            select(CustomJob).where(CustomJob.custom_automation_id == automation_id)
        )
    ).scalars().all()
    needles = _account_log_needles(account, account_id)
    synthetic = 1_000_000_000
    for job in jobs:
        for index, row in enumerate(job.logs or []):
            if not isinstance(row, dict):
                continue
            message = str(row.get("message") or "").strip()
            if not message:
                continue
            ts = _parse_log_ts(row.get("ts"))
            if ts is not None and ts < cutoff:
                continue
            if needles and not any(needle in message for needle in needles):
                continue
            key = (str(ts or ""), message)
            if key in seen:
                continue
            seen.add(key)
            synthetic += 1
            items.append(
                {
                    "id": synthetic,
                    "message": message,
                    "rpc_name": "",
                    "result": "error" if str(row.get("level") or "") == "error" else "ok",
                    "error": None,
                    "created_at": ts,
                }
            )
    items.sort(key=lambda item: item.get("created_at") or datetime.min, reverse=True)
    return items[:cap]
