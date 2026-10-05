"""Unified background jobs for the Telegram UBT Tasks screen."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import ChatDiscoveryTask, ChatImportJob, CustomJob
from .account_prepare_service import get_prepare_status
from .chat_inspect_service import get_inspect_status

logger = logging.getLogger(__name__)

LOG_TTL = timedelta(hours=24)
ACTIVE_STATUSES = {"pending", "running", "processing", "awaiting_approval"}
HISTORY_STATUSES = {"completed", "error", "cancelled", "skipped"}

JOB_META = {
    "discovery": {"category": "module", "title": "Поиск чатов", "badge": "ПП"},
    "import": {"category": "module", "title": "Импорт чатов", "badge": "ИМ"},
    "prepare": {"category": "account", "title": "Подготовка аккаунтов", "badge": "АК"},
    "health_check": {"category": "account", "title": "Проверка сессий", "badge": "АК"},
    "bulk_profile": {"category": "account", "title": "Обновление профилей", "badge": "АК"},
    "warmup": {"category": "account", "title": "Прогрев аккаунтов", "badge": "АК"},
    "neurocommenting": {"category": "module", "title": "Нейрокомментинг", "badge": "НК"},
    "discussion": {"category": "module", "title": "Нейрочаттинг", "badge": "ЧТ"},
    "masslooking": {"category": "module", "title": "Масслукинг", "badge": "МЛ"},
    "masspriming": {"category": "module", "title": "Масспрайминг", "badge": "МП"},
    "parser": {"category": "module", "title": "Парсер", "badge": "ПР"},
    "chat_broadcast": {"category": "module", "title": "Чат-рассылки", "badge": "ЧР"},
    "shilling": {"category": "module", "title": "Нейрошиллинг", "badge": "НШ"},
    "inspect": {"category": "module", "title": "Проверка комментариев", "badge": "КМ"},
    "join": {"category": "module", "title": "Вступление в чаты", "badge": "ВС"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.isoformat()


def _duration_seconds(started: datetime | None, ended: datetime | None, status: str) -> int:
    start = started
    finish = ended
    if not start:
        return 0
    if not finish:
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
        "duration_seconds": _duration_seconds(started_at or created_at, completed_at, normalized),
        "can_cancel": can_cancel,
        "can_approve": can_approve,
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
        logs.append(
            {
                "ts": _iso(task.completed_at or task.updated_at),
                "level": "info",
                "message": f"Завершено: {len(found)} чатов",
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
    return _payload(
        source="job",
        source_id=job.id,
        job_type=job.job_type,
        title=job.title or meta.get("title") or job.job_type,
        subtitle="",
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at or job.created_at,
        completed_at=job.completed_at,
        params=job.params or {},
        result=job.result or {},
        logs=job.logs or [],
        error=job.error,
        can_cancel=job.status in ACTIVE_STATUSES,
    )


def _matches(item: dict[str, Any], *, bucket: str, category: str | None, search: str | None) -> bool:
    status = item["status"]
    if bucket == "active" and status not in ACTIVE_STATUSES:
        return False
    if bucket == "history" and status in ACTIVE_STATUSES:
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

    items = [serialize_discovery(row) for row in discoveries]
    items.extend(serialize_import(row) for row in imports)
    items.extend(serialize_custom(row) for row in tracked)
    items.extend(_live_ephemeral(automation_id, items))
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
    async with async_session_maker() as session:
        job = CustomJob(
            custom_automation_id=automation_id,
            category=meta["category"],
            job_type=job_type,
            title=title or meta["title"],
            status="pending",
            params=params or {},
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
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if not job:
            return
        logs = list(job.logs or [])
        logs.append({"ts": _iso(_utc_now()), "level": level, "message": message})
        job.logs = logs[-200:]
        job.updated_at = _utc_now()
        await session.commit()


async def mark_running(job_id: int) -> None:
    async with async_session_maker() as session:
        job = await _load_job(session, job_id)
        if not job or job.status == "cancelled":
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
        if job.status == "cancelled":
            return
        job.status = status
        if result is not None:
            job.result = result
        if error:
            job.error = error[:500]
        job.completed_at = _utc_now()
        job.updated_at = _utc_now()
        await session.commit()


async def queue_tracked(background_tasks, automation_id: int, job_type: str, fn: Callable[..., Awaitable[Any]], *args: Any, params: dict[str, Any] | None = None) -> int:
    job_id = await spawn_job(automation_id, job_type, params=params)
    background_tasks.add_task(run_spawned, job_id, fn, *args)
    return job_id


async def run_spawned(job_id: int, fn: Callable[..., Awaitable[Any]], *args: Any) -> None:
    await mark_running(job_id)
    await append_log(job_id, "Задача запущена")
    try:
        result = await fn(*args)
        payload = result if isinstance(result, dict) else {"value": result}
        await finish_job(job_id, "completed", result=payload)
        await append_log(job_id, "Задача завершена")
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
        if job.status not in ACTIVE_STATUSES:
            return serialize_custom(job)
        job.status = "cancelled"
        job.completed_at = now
        job.updated_at = now
        logs = list(job.logs or [])
        logs.append({"ts": _iso(now), "level": "info", "message": "Отменено пользователем"})
        job.logs = logs
        await session.commit()
        await session.refresh(job)
        return serialize_custom(job)
    return None
