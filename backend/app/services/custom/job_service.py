"""Unified background jobs for the Telegram UBT Tasks screen."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import ChatDiscoveryTask, ChatImportJob, CustomAutomation, CustomJob
from .account_prepare_service import get_prepare_status
from .chat_inspect_service import get_inspect_status

logger = logging.getLogger(__name__)

LOG_TTL = timedelta(days=3)
MAX_JOB_LOGS = 2000
ACTIVE_STATUSES = {"pending", "running", "processing", "awaiting_approval"}
PAUSED_STATUS = "paused"
VISIBLE_ACTIVE_STATUSES = ACTIVE_STATUSES | {PAUSED_STATUS}
HISTORY_STATUSES = {"completed", "error", "cancelled", "skipped"}
_SKIP_PARAM_KEYS = {"presets", "_job_id"}
_READONLY_PARAM_KEYS = {"joins_complete"}
PERSISTENT_JOB_TYPES = {"neurocommenting", "discussion", "shilling", "chat_monitoring", "neuroblog"}
STREAM_JOB_TYPES = {
    "neurocommenting": "neurocommenting",
    "neurochatting": "discussion",
    "shilling": "shilling",
    "chat_broadcast": "chat_broadcast",
    "dm_broadcast": "dm_broadcast",
    "masslooking": "masslooking",
    "masspriming": "masspriming",
    "neuroblog": "neuroblog",
}
JOIN_JOB_TYPES = {
    "neurocommenting",
    "discussion",
    "shilling",
    "chat_broadcast",
    "chat_monitoring",
    "parser",
    "masslooking",
    "warmup",
    "join",
}
MODULE_BINDINGS = {
    "neurocommenting": ("neurocommenting", "is_neurocommenting_enabled"),
    "chat_monitoring": ("chat_monitoring", "is_chat_monitoring_enabled"),
    "discussion": ("neurochatting", "is_digital_footprint_enabled"),
    "chat_broadcast": ("chat_broadcasts", None),
    "dm_broadcast": ("dm_broadcasts", None),
    "masslooking": ("masslooking", None),
    "masspriming": ("masspriming", None),
    "parser": ("parser", None),
    "shilling": ("neuroshilling", "is_shilling_enabled"),
    "neuroblog": ("neuroblog", None),
}

JOB_META = {
    "discovery": {"category": "module", "title": "Поиск чатов", "badge": "ПП"},
    "import": {"category": "module", "title": "Импорт чатов", "badge": "ИМ"},
    "prepare": {"category": "account", "title": "Подготовка аккаунтов", "badge": "АК"},
    "health_check": {"category": "account", "title": "Проверка сессий", "badge": "АК"},
    "bulk_profile": {"category": "account", "title": "Обновление профилей", "badge": "АК"},
    "warmup": {"category": "account", "title": "Прогрев аккаунтов", "badge": "АК"},
    "neurocommenting": {"category": "module", "title": "Нейрокомментинг", "badge": "НК"},
    "chat_monitoring": {"category": "module", "title": "Перехват заявок", "badge": "ПЗ"},
    "discussion": {"category": "module", "title": "Нейрочаттинг", "badge": "ЧТ"},
    "masslooking": {"category": "module", "title": "Масслукинг", "badge": "МЛ"},
    "masspriming": {"category": "module", "title": "Масспрайминг", "badge": "МП"},
    "parser": {"category": "module", "title": "Парсер юзеров", "badge": "ПР"},
    "chat_broadcast": {"category": "module", "title": "Чат-рассылки", "badge": "ЧР"},
    "dm_broadcast": {"category": "module", "title": "ЛС-рассылки", "badge": "ЛС"},
    "shilling": {"category": "module", "title": "Нейрошиллинг", "badge": "НШ"},
    "neuroblog": {"category": "module", "title": "Нейроблог", "badge": "НБ"},
    "inspect": {"category": "module", "title": "Проверка комментариев", "badge": "КМ"},
    "join": {"category": "module", "title": "Вступление в чаты", "badge": "ВС"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.isoformat()


def clip_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def actor_label(account: Any) -> str:
    name = str(getattr(account, "display_name", None) or getattr(account, "username", None) or "").strip()
    if name.startswith("@"):
        name = name[1:]
    phone = str(getattr(account, "phone_number", None) or "").strip()
    if name and phone:
        return f"{name} ({phone})"
    return name or phone or f"аккаунт #{getattr(account, 'id', '?')}"


def chat_label(chat: Any) -> str:
    title = str(getattr(chat, "title", None) or "").strip()
    link = str(getattr(chat, "invite_link", None) or "").strip()
    if title and link:
        return f"«{title}» ({link})"
    return title or link or f"чат #{getattr(chat, 'id', '?')}"


def is_persistent_job(job_type: str, params: dict[str, Any] | None = None) -> bool:
    if job_type in PERSISTENT_JOB_TYPES:
        return True
    if job_type == "chat_broadcast":
        data = params or {}
        scenario = str(data.get("scenario") or "").strip().lower()
        if scenario == "loop":
            return True
        if scenario == "once":
            return False
        return not bool(data.get("skip_sent"))
    return False


def apply_module_enabled(automation: CustomAutomation, job_type: str, enabled: bool) -> None:
    key, flag = MODULE_BINDINGS.get(job_type, (None, None))
    blob = dict(automation.module_settings or {})
    if key:
        nested = dict(blob.get(key) or {}) if isinstance(blob.get(key), dict) else {}
        nested["enabled"] = enabled
        blob[key] = nested
        automation.module_settings = blob
    if flag:
        setattr(automation, flag, enabled)
    automation.updated_at = _utc_now()


def _duration_seconds(
    started: datetime | None,
    ended: datetime | None,
    status: str,
    *,
    freeze_at: datetime | None = None,
) -> int:
    start = started
    finish = ended
    if not start:
        return 0
    if status == PAUSED_STATUS:
        finish = freeze_at or ended or start
    elif not finish:
        finish = _utc_now() if status in ACTIVE_STATUSES else start
    delta = finish - start
    return max(0, int(delta.total_seconds()))


def _normalize_status(status: str | None) -> str:
    raw = (status or "pending").strip().lower()
    if raw in {"processing"}:
        return "running"
    if raw in {"idle"}:
        return "completed"
    return raw


def _public_params(raw: Any) -> dict[str, Any]:
    data = dict(raw) if isinstance(raw, dict) else {}
    for key in _SKIP_PARAM_KEYS:
        data.pop(key, None)
    return data


_PACING_JOB_TYPES = {
    "neurocommenting",
    "discussion",
    "shilling",
    "chat_broadcast",
    "dm_broadcast",
}


def _fill_pacing_params(job_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Show daily-cap / pause keys even on jobs launched before those fields existed."""
    from .module_delays import apply_account_pacing, clamp_join_delay_pair

    data = dict(params or {})
    if job_type in _PACING_JOB_TYPES:
        filled: dict[str, Any] = {}
        apply_account_pacing(filled, data, cap_default=15)
        for key, value in filled.items():
            if data.get(key) in (None, ""):
                data[key] = value
    if job_type in JOIN_JOB_TYPES:
        data["join_delay_min"], data["join_delay_max"] = clamp_join_delay_pair(data)
    return data


def _stamp_joins_complete(items: list[dict[str, Any]], automation: CustomAutomation | None) -> None:
    if not items:
        return
    from .chat_addlist_service import joins_complete_by_job_type

    flags = joins_complete_by_job_type(automation)
    for item in items:
        job_type = str(item.get("job_type") or "")
        if job_type not in flags:
            continue
        params = dict(item.get("params") or {})
        params["joins_complete"] = flags[job_type]
        item["params"] = params


def _append_job_log(job: CustomJob, message: str, *, level: str = "info") -> None:
    logs = list(job.logs or [])
    logs.append({"ts": _iso(_utc_now()), "level": level, "message": str(message)[:2000]})
    job.logs = logs[-MAX_JOB_LOGS:]


def _filter_logs(logs: list[Any] | None) -> list[dict[str, Any]]:
    cutoff = _utc_now() - LOG_TTL
    items: list[dict[str, Any]] = []
    for row in logs or []:
        if not isinstance(row, dict):
            continue
        ts_raw = row.get("ts")
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "")) if ts_raw else None
        except ValueError:
            ts = None
        if ts and ts < cutoff:
            continue
        items.append(
            {
                "ts": _iso(ts) if ts else ts_raw,
                "level": row.get("level") or "info",
                "message": row.get("message") or "",
            }
        )
    return items


def _payload(
    *,
    source: str,
    source_id: int,
    job_type: str,
    title: str,
    status: str,
    created_at: datetime | None,
    started_at: datetime | None,
    completed_at: datetime | None,
    params: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    logs: list[Any] | None = None,
    error: str | None = None,
    subtitle: str | None = None,
    can_cancel: bool = False,
    can_approve: bool = False,
    can_pause: bool = False,
    can_resume: bool = False,
    can_edit: bool = False,
    freeze_at: datetime | None = None,
) -> dict[str, Any]:
    meta = JOB_META.get(job_type, {"category": "module", "title": title, "badge": "ЗД"})
    normalized = _normalize_status(status)
    return {
        "id": f"{source}:{source_id}",
        "source": source,
        "source_id": source_id,
        "category": meta["category"],
        "job_type": job_type,
        "badge": meta["badge"],
        "title": title or meta["title"],
        "subtitle": subtitle or "",
        "status": normalized,
        "params": params or {},
        "result": result or {},
        "logs": _filter_logs(logs),
        "error": error,
        "created_at": created_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": _duration_seconds(
            started_at or created_at, completed_at, normalized, freeze_at=freeze_at
        ),
        "can_cancel": can_cancel,
        "can_approve": can_approve,
        "can_pause": can_pause,
        "can_resume": can_resume,
        "can_edit": can_edit,
    }


def _discovery_logs(task: ChatDiscoveryTask) -> list[dict[str, Any]]:
    logs = [
        {"ts": _iso(task.created_at), "level": "info", "message": f"Создан поиск по запросу «{task.query}»"},
    ]
    if task.status in {"processing", "running"}:
        logs.append({"ts": _iso(task.updated_at), "level": "info", "message": "Идёт поиск в Telegram"})
    for chat in (task.found_chats or [])[:40]:
        if not isinstance(chat, dict):
            continue
        label = chat.get("title") or chat.get("username") or chat.get("id") or "чат"
        logs.append(
            {
                "ts": _iso(task.updated_at or task.completed_at or task.created_at),
                "level": "info",
                "message": f"Найден {label}",
            }
        )
    if task.status == "awaiting_approval":
        logs.append({"ts": _iso(task.updated_at), "level": "info", "message": "Ожидает ручного одобрения"})
    elif task.status == "completed":
        found_count = len([row for row in (task.found_chats or []) if isinstance(row, dict)])
        logs.append(
            {
                "ts": _iso(task.completed_at or task.updated_at),
                "level": "info",
                "message": f"Завершено: {found_count} чатов",
            }
        )
    elif task.status == "error":
        logs.append({"ts": _iso(task.updated_at), "level": "error", "message": "Поиск завершился с ошибкой"})
    elif task.status == "cancelled":
        logs.append({"ts": _iso(task.updated_at), "level": "info", "message": "Задача отменена"})
    return logs


def serialize_discovery(task: ChatDiscoveryTask) -> dict[str, Any]:
    found = [row for row in (task.found_chats or []) if isinstance(row, dict)]
    status = task.status
    return _payload(
        source="discovery",
        source_id=task.id,
        job_type="discovery",
        title="Поиск чатов",
        subtitle=task.query,
        status=status,
        created_at=task.created_at,
        started_at=task.created_at,
        completed_at=task.completed_at,
        params={
            "Запрос": task.query,
            "Макс. чатов": task.max_chats,
            "Порог релевантности": task.relevance_threshold,
            "Ручное одобрение": bool(task.require_approval),
            "Режим": task.mode,
        },
        result={
            "Всего каналов": len(found),
            "Одобрено": task.joined_chats,
            "Отклонено": task.rejected_chats,
            "items": found,
        },
        logs=_discovery_logs(task),
        can_cancel=status in {"pending", "processing"},
        can_approve=status == "awaiting_approval",
        can_edit=status in {"pending", "processing", "awaiting_approval"},
    )


def serialize_import(job: ChatImportJob) -> dict[str, Any]:
    logs = []
    for row in job.error_log or []:
        if isinstance(row, dict):
            logs.append(
                {
                    "ts": _iso(job.updated_at or job.created_at),
                    "level": "error" if row.get("error") or row.get("error_rows") else "info",
                    "message": str(row.get("error") or row.get("message") or row),
                }
            )
        else:
            logs.append({"ts": _iso(job.created_at), "level": "info", "message": str(row)})
    if not logs:
        logs = [{"ts": _iso(job.created_at), "level": "info", "message": f"Файл {job.file_name}"}]
    return _payload(
        source="import",
        source_id=job.id,
        job_type="import",
        title="Импорт чатов",
        subtitle=job.file_name,
        status=job.status,
        created_at=job.created_at,
        started_at=job.created_at,
        completed_at=job.updated_at if job.status not in ACTIVE_STATUSES else None,
        params={"Файл": job.file_name, "Строк": job.total_rows},
        result={
            "Обработано": job.processed_rows,
            "Ошибок": job.error_rows,
            "Дублей": job.duplicate_rows,
        },
        logs=logs,
        can_cancel=job.status in {"pending"},
    )


def serialize_custom(job: CustomJob) -> dict[str, Any]:
    meta = JOB_META.get(job.job_type, {})
    status = job.status
    return _payload(
        source="job",
        source_id=job.id,
        job_type=job.job_type,
        title=job.title or meta.get("title") or job.job_type,
        subtitle="На паузе" if status == PAUSED_STATUS else "",
        status=status,
        created_at=job.created_at,
        started_at=job.started_at or job.created_at,
        completed_at=None if status == PAUSED_STATUS else job.completed_at,
        params=_fill_pacing_params(job.job_type, _public_params(job.params)),
        result=job.result or {},
        logs=job.logs or [],
        error=job.error,
        can_cancel=status in VISIBLE_ACTIVE_STATUSES,
        can_pause=status in ACTIVE_STATUSES,
        can_resume=status == PAUSED_STATUS,
        can_edit=status in VISIBLE_ACTIVE_STATUSES,
        freeze_at=job.updated_at if status == PAUSED_STATUS else None,
    )


def _matches(item: dict[str, Any], *, bucket: str, category: str | None, search: str | None) -> bool:
    status = item["status"]
    if bucket == "active" and status not in VISIBLE_ACTIVE_STATUSES:
        return False
    if bucket == "history" and status in VISIBLE_ACTIVE_STATUSES:
        return False
    if category and item.get("category") != category:
        return False
    if search:
        blob = " ".join(
            [
                item.get("title") or "",
                item.get("subtitle") or "",
                item.get("job_type") or "",
                str(item.get("params") or ""),
            ]
        ).lower()
        if search.lower() not in blob:
            return False
    return True


def _live_ephemeral(automation_id: int, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extras: list[dict[str, Any]] = []
    has_running_prepare = any(
        item["job_type"] == "prepare" and item["status"] in ACTIVE_STATUSES for item in existing
    )
    prepare = get_prepare_status(automation_id)
    if prepare.get("status") == "running" and not has_running_prepare:
        extras.append(
            _payload(
                source="prepare-live",
                source_id=automation_id,
                job_type="prepare",
                title="Подготовка аккаунтов",
                status="running",
                created_at=_utc_now(),
                started_at=_utc_now(),
                completed_at=None,
                params={},
                result={
                    "Живых": prepare.get("alive") or 0,
                    "Профили": prepare.get("profiles_done") or 0,
                    "Чаты": prepare.get("chats_joined") or 0,
                },
                logs=[{"ts": _iso(_utc_now()), "level": "info", "message": "Идёт подготовка после залива"}],
            )
        )
    has_running_inspect = any(
        item["job_type"] == "inspect" and item["status"] in ACTIVE_STATUSES for item in existing
    )
    inspect = get_inspect_status(automation_id)
    if inspect.get("status") == "running" and not has_running_inspect:
        extras.append(
            _payload(
                source="inspect-live",
                source_id=automation_id,
                job_type="inspect",
                title="Проверка комментариев",
                status="running",
                created_at=_utc_now(),
                started_at=_utc_now(),
                completed_at=None,
                result={
                    "Всего": inspect.get("total") or 0,
                    "Проверено": inspect.get("checked") or 0,
                },
                logs=[{"ts": _iso(_utc_now()), "level": "info", "message": "Читаем комментарии без записи в Telegram"}],
            )
        )
    return extras


async def list_jobs(
    session: AsyncSession,
    automation_id: int,
    *,
    bucket: str = "all",
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    discoveries = (
        await session.execute(
            select(ChatDiscoveryTask)
            .where(ChatDiscoveryTask.custom_automation_id == automation_id)
            .order_by(ChatDiscoveryTask.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    imports = (
        await session.execute(
            select(ChatImportJob)
            .where(ChatImportJob.custom_automation_id == automation_id)
            .order_by(ChatImportJob.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    tracked = (
        await session.execute(
            select(CustomJob)
            .where(CustomJob.custom_automation_id == automation_id)
            .order_by(CustomJob.created_at.desc())
            .limit(200)
        )
    ).scalars().all()

    automation = await session.get(CustomAutomation, automation_id)
    items = [serialize_discovery(row) for row in discoveries]
    items.extend(serialize_import(row) for row in imports)
    items.extend(serialize_custom(row) for row in tracked)
    items.extend(_live_ephemeral(automation_id, items))
    _stamp_joins_complete(items, automation)
    items.sort(key=lambda row: row.get("created_at") or datetime.min, reverse=True)
    filtered = [row for row in items if _matches(row, bucket=bucket or "all", category=category, search=search)]
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {"items": page, "total": total}


async def get_job(session: AsyncSession, automation_id: int, job_id: str) -> dict[str, Any] | None:
    data = await list_jobs(session, automation_id, bucket="all", limit=400, offset=0)
    for item in data["items"]:
        if item["id"] == job_id:
            return item
    return None


async def spawn_job(
    automation_id: int,
    job_type: str,
    *,
    params: dict[str, Any] | None = None,
    title: str | None = None,
) -> int:
    meta = JOB_META.get(job_type, {"category": "module", "title": job_type})
    raw = dict(params or {})
    if job_type in MODULE_BINDINGS or job_type == "warmup":
        raw = _public_params(_normalize_module_params(job_type, raw))
    raw = _fill_pacing_params(job_type, _public_params(raw))
    async with async_session_maker() as session:
        job = CustomJob(
            custom_automation_id=automation_id,
            category=meta["category"],
            job_type=job_type,
            title=title or meta["title"],
            status="pending",
            params=raw,
            result={},
            logs=[{"ts": _iso(_utc_now()), "level": "info", "message": "Задача поставлена в очередь"}],
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def _load_job(session: AsyncSession, job_id: int) -> CustomJob | None:
    return await session.get(CustomJob, job_id)


async def append_log(job_id: int, message: str, *, level: str = "info") -> None:
    text = str(message or "").strip()
    if not text:
        return
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if not job:
            return
        logs = list(job.logs or [])
        logs.append({"ts": _iso(_utc_now()), "level": level, "message": text[:2000]})
        job.logs = logs[-MAX_JOB_LOGS:]
        job.updated_at = _utc_now()
        await session.commit()


async def find_active_job_id(automation_id: int, job_type: str) -> int | None:
    async with async_session_maker() as session:
        job_id = await session.scalar(
            select(CustomJob.id)
            .where(
                CustomJob.custom_automation_id == automation_id,
                CustomJob.job_type == job_type,
                CustomJob.status.in_(tuple(ACTIVE_STATUSES)),
            )
            .order_by(CustomJob.id.desc())
            .limit(1)
        )
        return int(job_id) if job_id else None


async def list_active_job_types(automation_id: int) -> set[str]:
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(CustomJob.job_type).where(
                    CustomJob.custom_automation_id == automation_id,
                    CustomJob.status.in_(tuple(ACTIVE_STATUSES)),
                )
            )
        ).scalars().all()
        return {str(item) for item in rows if item}


async def load_active_job_params(
    session: AsyncSession, automation_id: int, job_type: str
) -> dict[str, Any] | None:
    """Params of the running Tasks job, so the session loop matches the card."""
    job = await session.scalar(
        select(CustomJob)
        .where(
            CustomJob.custom_automation_id == automation_id,
            CustomJob.job_type == job_type,
            CustomJob.status.in_(tuple(ACTIVE_STATUSES)),
        )
        .order_by(CustomJob.id.desc())
        .limit(1)
    )
    if job is None or not isinstance(job.params, dict):
        return None
    return dict(job.params)


async def log_active(automation_id: int, job_type: str, message: str, *, level: str = "info") -> None:
    job_id = await find_active_job_id(automation_id, job_type)
    if job_id:
        await append_log(job_id, message, level=level)


async def job_is_cancelled(job_id: int) -> bool:
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        return job is None or job.status == "cancelled"


async def job_is_stopped(job_id: int) -> bool:
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        return job is None or job.status in {"cancelled", PAUSED_STATUS}


async def mark_running(job_id: int) -> None:
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if not job or job.status in {"cancelled", PAUSED_STATUS}:
            return
        job.status = "running"
        job.started_at = job.started_at or _utc_now()
        job.updated_at = _utc_now()
        await session.commit()


async def finish_job(
    job_id: int,
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if not job:
            return
        if job.status in {"cancelled", PAUSED_STATUS}:
            return
        job.status = status
        if result is not None:
            job.result = result
        if error:
            job.error = error[:500]
        if status not in ACTIVE_STATUSES:
            job.completed_at = _utc_now()
        job.updated_at = _utc_now()
        await session.commit()


async def _disable_module_for_job(job_id: int) -> None:
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if job is None:
            return
        automation = await session.get(CustomAutomation, job.custom_automation_id)
        if automation is None:
            return
        apply_module_enabled(automation, job.job_type, False)
        await session.commit()


async def _cancel_sibling_jobs(automation_id: int, job_type: str, keep_id: int) -> None:
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(CustomJob).where(
                    CustomJob.custom_automation_id == automation_id,
                    CustomJob.job_type == job_type,
                    CustomJob.status.in_(tuple(VISIBLE_ACTIVE_STATUSES)),
                    CustomJob.id != keep_id,
                )
            )
        ).scalars().all()
        now = _utc_now()
        for job in rows:
            job.status = "cancelled"
            job.completed_at = now
            job.updated_at = now
            logs = list(job.logs or [])
            logs.append({"ts": _iso(now), "level": "info", "message": "Заменён новым запуском"})
            job.logs = logs[-MAX_JOB_LOGS:]
        if rows:
            await session.commit()


async def _enable_module_for_job(automation_id: int, job_type: str) -> None:
    if job_type not in MODULE_BINDINGS:
        return
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if automation is None:
            return
        apply_module_enabled(automation, job_type, True)
        await session.commit()


async def queue_tracked(background_tasks, automation_id: int, job_type: str, fn: Callable[..., Awaitable[Any]], *args: Any, params: dict[str, Any] | None = None) -> int:
    job_id = await spawn_job(automation_id, job_type, params=params)
    await _cancel_sibling_jobs(automation_id, job_type, job_id)
    await _enable_module_for_job(automation_id, job_type)
    bound_args = args
    if args and isinstance(args[-1], dict):
        bound_args = (*args[:-1], {**args[-1], "_job_id": job_id})
    background_tasks.add_task(run_spawned, job_id, fn, *bound_args)
    return job_id


def _finite_should_complete(payload: dict[str, Any], job_type: str) -> bool:
    status = str(payload.get("status") or "ok").strip().lower()
    if status in {"error"}:
        return True
    if status == "skipped" and payload.get("reason") in {"night", "schedule"}:
        return job_type not in set(STREAM_JOB_TYPES.values())
    remaining = payload.get("remaining")
    if remaining is not None:
        try:
            return int(remaining) <= 0
        except (TypeError, ValueError):
            return True
    return status in {"ok", "completed", "done", "stopped", "skipped"}


async def run_spawned(job_id: int, fn: Callable[..., Awaitable[Any]], *args: Any) -> None:
    await mark_running(job_id)
    if await job_is_stopped(job_id):
        return
    await append_log(job_id, "Задача запущена")
    job_type = ""
    params: dict[str, Any] = {}
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if job is not None:
            job_type = job.job_type
            params = dict(job.params or {})
    persistent = is_persistent_job(job_type, params)
    try:
        result = await fn(*args)
        payload = result if isinstance(result, dict) else {"value": result}
        if await job_is_stopped(job_id):
            return
        if persistent:
            await finish_job(job_id, "running", result=payload)
            await append_log(job_id, "Цикл работает. Остановлю только по кнопке.")
            return
        if _finite_should_complete(payload, job_type):
            await finish_job(job_id, "completed", result=payload)
            await append_log(job_id, "Задача завершена: обработаны целевые объекты")
            await _disable_module_for_job(job_id)
            return
        await finish_job(job_id, "running", result=payload)
    except Exception as exc:
        logger.exception("Tracked job %s failed: %s", job_id, exc)
        await finish_job(job_id, "error", error=str(exc))
        await append_log(job_id, str(exc)[:400], level="error")


async def record_finished(
    automation_id: int,
    job_type: str,
    *,
    result: dict[str, Any] | None = None,
    status: str = "completed",
    error: str | None = None,
    params: dict[str, Any] | None = None,
    message: str | None = None,
) -> int:
    job_id = await spawn_job(automation_id, job_type, params=params)
    await mark_running(job_id)
    await finish_job(job_id, status, result=result, error=error)
    await append_log(job_id, message or ("Задача завершена" if status == "completed" else (error or "Ошибка")), level="error" if status == "error" else "info")
    return job_id


async def cancel_job(session: AsyncSession, automation_id: int, job_id: str) -> dict[str, Any] | None:
    source, _, raw = job_id.partition(":")
    if not raw.isdigit():
        return None
    ident = int(raw)
    now = _utc_now()
    if source == "discovery":
        task = await session.get(ChatDiscoveryTask, ident)
        if not task or task.custom_automation_id != automation_id:
            return None
        if task.status not in {"pending", "processing"}:
            return serialize_discovery(task)
        task.status = "cancelled"
        task.updated_at = now
        task.completed_at = now
        await session.commit()
        await session.refresh(task)
        return serialize_discovery(task)
    if source == "job":
        job = await session.get(CustomJob, ident)
        if not job or job.custom_automation_id != automation_id:
            return None
        if job.status not in VISIBLE_ACTIVE_STATUSES:
            return serialize_custom(job)
        job.status = "cancelled"
        job.completed_at = now
        job.updated_at = now
        logs = list(job.logs or [])
        logs.append({"ts": _iso(now), "level": "info", "message": "Остановлено. Модуль выключен, вступления по этой задаче больше не идут."})
        job.logs = logs[-MAX_JOB_LOGS:]
        automation = await session.get(CustomAutomation, automation_id)
        if automation is not None:
            apply_module_enabled(automation, job.job_type, False)
        await session.commit()
        await session.refresh(job)
        return serialize_custom(job)
    return None


def _split_job_id(job_id: str) -> tuple[str, int] | None:
    source, _, raw = job_id.partition(":")
    if not raw.isdigit():
        return None
    return source, int(raw)


def _normalize_module_params(job_type: str, incoming: dict[str, Any]) -> dict[str, Any]:
    if job_type == "neurocommenting":
        from .neurocommenting_module_service import normalize_nc_settings

        return normalize_nc_settings(incoming)
    if job_type == "chat_monitoring":
        from .chat_monitoring_module_service import normalize_cm_settings

        return normalize_cm_settings(incoming)
    if job_type == "discussion":
        from .neurochatting_module_service import normalize_chat_settings

        return normalize_chat_settings(incoming)
    if job_type == "shilling":
        from .neuroshilling_module_service import normalize_shill_settings

        return normalize_shill_settings(incoming)
    if job_type == "chat_broadcast":
        from .chat_broadcast_module_service import normalize_bc_settings

        return normalize_bc_settings(incoming)
    if job_type == "dm_broadcast":
        from .dm_broadcast_module_service import normalize_dm_settings

        return normalize_dm_settings(incoming)
    if job_type == "masslooking":
        from .masslooking_module_service import normalize_look_settings

        return normalize_look_settings(incoming)
    if job_type == "masspriming":
        from .masspriming_module_service import normalize_prime_settings

        return normalize_prime_settings(incoming)
    if job_type == "parser":
        from .parser_module_service import normalize_parser_settings

        return normalize_parser_settings(incoming)
    if job_type == "warmup":
        from .warmup_module_service import normalize_warmup_settings

        return normalize_warmup_settings(incoming)
    if job_type == "neuroblog":
        from .neuroblog_service import normalize_neuroblog_settings

        return normalize_neuroblog_settings(incoming, previous=incoming)
    return incoming


def _apply_params_to_module(automation: CustomAutomation, job_type: str, params: dict[str, Any]) -> None:
    key, _flag = MODULE_BINDINGS.get(job_type, (None, None))
    if job_type == "warmup":
        key = "warmup"
    if not key:
        return
    blob = dict(automation.module_settings or {})
    current = dict(blob.get(key) or {}) if isinstance(blob.get(key), dict) else {}
    merged = {
        **current,
        **{
            k: v
            for k, v in params.items()
            if k not in _SKIP_PARAM_KEYS and k not in _READONLY_PARAM_KEYS
        },
    }
    merged["presets"] = current.get("presets") or []
    if "enabled" in current:
        merged["enabled"] = current.get("enabled")
    blob[key] = _normalize_module_params(job_type, merged)
    automation.module_settings = blob
    automation.updated_at = _utc_now()


_DISCOVERY_PARAM_KEYS = {
    "query": "query",
    "Запрос": "query",
    "max_chats": "max_chats",
    "Макс. чатов": "max_chats",
    "relevance_threshold": "relevance_threshold",
    "Порог релевантности": "relevance_threshold",
    "require_approval": "require_approval",
    "Ручное одобрение": "require_approval",
    "mode": "mode",
    "Режим": "mode",
}


async def pause_job(session: AsyncSession, automation_id: int, job_id: str) -> dict[str, Any] | None:
    parsed = _split_job_id(job_id)
    if not parsed or parsed[0] != "job":
        return None
    job = await session.get(CustomJob, parsed[1])
    if not job or job.custom_automation_id != automation_id:
        return None
    if job.status not in ACTIVE_STATUSES:
        return serialize_custom(job)
    now = _utc_now()
    job.status = PAUSED_STATUS
    job.completed_at = None
    job.updated_at = now
    _append_job_log(job, "На паузе. Можно продолжить или изменить параметры.")
    await session.commit()
    await session.refresh(job)
    return serialize_custom(job)


async def resume_job(session: AsyncSession, automation_id: int, job_id: str) -> dict[str, Any] | None:
    parsed = _split_job_id(job_id)
    if not parsed or parsed[0] != "job":
        return None
    job = await session.get(CustomJob, parsed[1])
    if not job or job.custom_automation_id != automation_id:
        return None
    if job.status != PAUSED_STATUS:
        return serialize_custom(job)
    now = _utc_now()
    job.status = "running"
    job.started_at = job.started_at or now
    job.completed_at = None
    job.updated_at = now
    _append_job_log(job, "Возобновлено.")
    automation = await session.get(CustomAutomation, automation_id)
    if automation is not None:
        apply_module_enabled(automation, job.job_type, True)
    await session.commit()
    await session.refresh(job)
    return serialize_custom(job)


async def update_job(
    session: AsyncSession,
    automation_id: int,
    job_id: str,
    *,
    params: dict[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any] | None:
    parsed = _split_job_id(job_id)
    if not parsed:
        return None
    source, ident = parsed
    now = _utc_now()
    if source == "discovery":
        task = await session.get(ChatDiscoveryTask, ident)
        if not task or task.custom_automation_id != automation_id:
            return None
        if task.status not in {"pending", "processing", "awaiting_approval"}:
            return serialize_discovery(task)
        incoming = params or {}
        mapped: dict[str, Any] = {}
        for key, value in incoming.items():
            field = _DISCOVERY_PARAM_KEYS.get(str(key))
            if field:
                mapped[field] = value
        if "query" in mapped:
            query = str(mapped["query"] or "").strip()
            if query:
                task.query = query
        if "max_chats" in mapped:
            try:
                task.max_chats = max(1, min(200, int(mapped["max_chats"])))
            except (TypeError, ValueError):
                pass
        if "relevance_threshold" in mapped:
            try:
                task.relevance_threshold = max(0.0, min(1.0, float(mapped["relevance_threshold"])))
            except (TypeError, ValueError):
                pass
        if "require_approval" in mapped:
            task.require_approval = bool(mapped["require_approval"])
        if "mode" in mapped:
            mode = str(mapped["mode"] or "").strip() or task.mode
            task.mode = mode
        task.updated_at = now
        await session.commit()
        await session.refresh(task)
        return serialize_discovery(task)
    if source != "job":
        return None
    job = await session.get(CustomJob, ident)
    if not job or job.custom_automation_id != automation_id:
        return None
    if job.status not in VISIBLE_ACTIVE_STATUSES:
        return serialize_custom(job)
    if title:
        job.title = str(title).strip()[:255] or job.title
    incoming = {
        k: v for k, v in _public_params(params or {}).items() if k not in _READONLY_PARAM_KEYS
    }
    if incoming:
        merged = {**_public_params(job.params), **incoming}
        if job.job_type in MODULE_BINDINGS or job.job_type == "warmup":
            merged = _public_params(_normalize_module_params(job.job_type, merged))
        job.params = merged
        automation = await session.get(CustomAutomation, automation_id)
        if automation is not None:
            _apply_params_to_module(automation, job.job_type, merged)
        _append_job_log(job, "Параметры обновлены.")
    job.updated_at = now
    await session.commit()
    await session.refresh(job)
    return serialize_custom(job)
