"""Bulk import ChatTarget rows from CSV/XLSX files."""
import csv
import io
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import ChatImportJob, ChatSource, ChatTarget, ChatJoinStatus, ChatMode
from ...config import settings

logger = logging.getLogger(__name__)


_PROVIDER = "telegram"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _normalize_link(link: str | None) -> str | None:
    if not link:
        return None
    link = link.strip()
    if link in {"-", "nan", "null", "None"}:
        return None
    return link


def _normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    title = title.strip()
    if title in {"-", "nan", "null", "None"}:
        return None
    return title


def _read_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = {k.strip().lower(): (v.strip() if v else None) for k, v in raw.items()}
        rows.append(row)
    return rows


def _read_excel(content: bytes) -> list[dict[str, Any]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is not installed; cannot import Excel files") from exc

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(cell).strip().lower() if cell else "" for cell in rows[0]]
    result = []
    for values in rows[1:]:
        row = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            value = values[idx] if idx < len(values) else None
            row[header] = str(value).strip() if value is not None else None
        result.append(row)
    return result


def _parse_rows(content: bytes, filename: str) -> list[dict[str, Any]]:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return _read_csv(content)
    if name.endswith((".xlsx", ".xls")):
        return _read_excel(content)
    try:
        return _read_csv(content)
    except Exception:
        return _read_excel(content)


async def _save_import_file(automation_id: int, job_id: int, filename: str, content: bytes) -> str:
    root = _media_root()
    imports_dir = root / "chat_imports" / str(automation_id) / str(job_id)
    imports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{int(time.time())}_{filename.replace(' ', '_')}"
    target = imports_dir / safe_name
    target.write_bytes(content)
    return str(target.relative_to(root))


async def import_chats_from_file(
    session: AsyncSession,
    *,
    automation_id: int,
    filename: str,
    content: bytes,
    created_by_admin_id: int | None = None,
) -> ChatImportJob:
    rows = _parse_rows(content, filename)
    job = ChatImportJob(
        custom_automation_id=automation_id,
        file_name=filename,
        file_path=None,
        status="pending",
        total_rows=len(rows),
        processed_rows=0,
        error_rows=0,
        error_log=[],
        created_by_admin_id=created_by_admin_id,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    file_path = await _save_import_file(automation_id, job.id, filename, content)
    job.file_path = file_path

    created = 0
    errors = []
    for idx, row in enumerate(rows, start=1):
        try:
            invite_link = _normalize_link(row.get("invite_link") or row.get("link") or row.get("url"))
            external_chat_id = _normalize_link(row.get("external_chat_id") or row.get("chat_id"))
            title = _normalize_title(row.get("title") or row.get("name") or row.get("chat_name"))
            description = _normalize_title(row.get("description") or row.get("about"))
            chat_type = _normalize_link(row.get("chat_type") or row.get("type"))

            if not invite_link and not external_chat_id and not title:
                raise ValueError("empty row")

            target = ChatTarget(
                custom_automation_id=automation_id,
                provider=_PROVIDER,
                external_chat_id=external_chat_id,
                invite_link=invite_link,
                title=title,
                description=description,
                chat_type=chat_type,
                mode=ChatMode.MONITORING.value,
                source=ChatSource.BULK_IMPORT.value,
                import_job_id=job.id,
                join_status=ChatJoinStatus.PENDING.value,
                join_attempts=0,
                is_active=True,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(target)
            created += 1
        except Exception as exc:
            errors.append({"row": idx, "error": str(exc)})

    job.processed_rows = created
    job.error_rows = len(errors)
    job.error_log = errors
    job.status = "completed" if not errors else "completed_with_errors"
    job.updated_at = _utc_now()
    await session.commit()
    await session.refresh(job)
    return job


async def retry_import_errors(
    session: AsyncSession,
    job_id: int,
) -> ChatImportJob | None:
    job = await session.get(ChatImportJob, job_id)
    if not job or not job.file_path:
        return None
    content = (_media_root() / job.file_path).read_bytes()
    rows = _parse_rows(content, job.file_name)

    created = 0
    for idx, row in enumerate(rows, start=1):
        if any(err.get("row") == idx for err in job.error_log):
            try:
                invite_link = _normalize_link(row.get("invite_link") or row.get("link") or row.get("url"))
                external_chat_id = _normalize_link(row.get("external_chat_id") or row.get("chat_id"))
                title = _normalize_title(row.get("title") or row.get("name") or row.get("chat_name"))
                description = _normalize_title(row.get("description") or row.get("about"))
                chat_type = _normalize_link(row.get("chat_type") or row.get("type"))
                if not invite_link and not external_chat_id and not title:
                    raise ValueError("empty row")
                target = ChatTarget(
                    custom_automation_id=job.custom_automation_id,
                    provider=_PROVIDER,
                    external_chat_id=external_chat_id,
                    invite_link=invite_link,
                    title=title,
                    description=description,
                    chat_type=chat_type,
                    mode=ChatMode.MONITORING.value,
                    source=ChatSource.BULK_IMPORT.value,
                    import_job_id=job.id,
                    join_status=ChatJoinStatus.PENDING.value,
                    join_attempts=0,
                    is_active=True,
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
                session.add(target)
                created += 1
            except Exception as exc:
                logger.warning("Retry import row %s failed: %s", idx, exc)

    job.processed_rows += created
    job.error_rows = max(0, job.error_rows - created)
    job.updated_at = _utc_now()
    await session.commit()
    await session.refresh(job)
    return job
