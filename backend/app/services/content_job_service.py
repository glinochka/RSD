"""Queue and lifecycle manager for content_factory pipeline jobs."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import json
import logging
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection, AgentContentJob
from ..utils.agent_template_config import parse_agent_template_config
from ..utils.crypto import decrypt_token, encrypt_token
from .youtube_client import get_youtube_client

logger = logging.getLogger(__name__)

CONTENT_JOB_STATUSES = {
    "planned",
    "script_ready",
    "rendering",
    "rendered",
    "publishing",
    "published",
    "failed",
}

RETRYABLE_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "temporar",
    "network",
    "connection",
    "429",
    "503",
    "502",
    "504",
    "rate limit",
    "unavailable",
)

FAIL_FAST_ERROR_MARKERS = (
    "oauth",
    "token",
    "unauthorized",
    "forbidden",
    "invalid credential",
    "invalid api key",
    "permission",
    "config",
    "misconfig",
    "authentication",
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _resolve_timezone(name: str | None) -> timezone | ZoneInfo:
    normalized = str(name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(normalized)
    except Exception:
        logger.warning("Invalid timezone=%s in content_factory config, fallback to UTC", normalized)
        return timezone.utc


def _parse_daily_time(raw: str | None) -> time:
    value = str(raw or "10:00").strip() or "10:00"
    try:
        hours, minutes = value.split(":")
        return time(hour=int(hours), minute=int(minutes))
    except Exception:
        return time(hour=10, minute=0)


def _compute_retry_delay_seconds(retry_count: int) -> int:
    # 1m, 2m, 4m ... capped at 60m
    return min(60 * (2 ** max(0, retry_count - 1)), 3600)


class ContentJobService:
    """Manage content jobs: enqueue, claim, lifecycle transitions and retries."""

    async def enqueue_daily_jobs(self, now: datetime) -> dict[str, int]:
        now_utc = _to_utc_naive(now)
        created = 0
        skipped = 0

        async with async_session_maker() as session:
            async with session.begin():
                agents = (
                    await session.execute(
                        select(Agent).where(
                            Agent.template_type == "content_factory",
                            Agent.is_active.is_(True),
                        )
                    )
                ).scalars().all()

                for agent in agents:
                    cfg = parse_agent_template_config(agent.template_config)
                    if not bool(cfg.get("daily_posting_enabled", True)):
                        continue

                    tz = _resolve_timezone(str(cfg.get("timezone") or "UTC"))
                    posting_time = _parse_daily_time(str(cfg.get("daily_post_time") or "10:00"))

                    now_with_tz = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
                    content_date = now_with_tz.date()
                    scheduled_local = datetime.combine(content_date, posting_time, tzinfo=tz)
                    scheduled_for = _to_utc_naive(scheduled_local)

                    # Daily dedup: 1 job per agent per local content date (provider=youtube).
                    start_local = datetime.combine(content_date, time.min, tzinfo=tz)
                    end_local = start_local + timedelta(days=1)
                    start_utc = _to_utc_naive(start_local)
                    end_utc = _to_utc_naive(end_local)
                    duplicate = await session.scalar(
                        select(AgentContentJob.id).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.scheduled_for >= start_utc,
                            AgentContentJob.scheduled_for < end_utc,
                        )
                    )
                    if duplicate:
                        skipped += 1
                        continue

                    metadata = {
                        "provider": "youtube",
                        "content_date": str(content_date),
                        "timezone": str(cfg.get("timezone") or "UTC"),
                    }
                    row = AgentContentJob(
                        agent_id=agent.id,
                        status="planned",
                        scheduled_for=scheduled_for,
                        retry_count=0,
                        max_retries=3,
                        metadata_json=json.dumps(metadata, ensure_ascii=False),
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    session.add(row)
                    created += 1

        return {"created": created, "skipped_duplicates": skipped}

    async def claim_next_job(self, now: datetime | None = None) -> AgentContentJob | None:
        current = _to_utc_naive(now or _now_utc())
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(AgentContentJob)
                    .where(
                        AgentContentJob.status == "planned",
                        AgentContentJob.started_at.is_(None),
                        AgentContentJob.scheduled_for <= current,
                    )
                    .order_by(AgentContentJob.scheduled_for.asc(), AgentContentJob.id.asc())
                    .limit(1)
                )
                if row is None:
                    return None

                row.started_at = current
                row.updated_at = current
                await session.flush()
                return row

    async def mark_status(
        self,
        *,
        job_id: int,
        status: str,
        script_text: str | None = None,
        script_model: str | None = None,
        kling_task_id: str | None = None,
        video_url: str | None = None,
        youtube_video_id: str | None = None,
        youtube_video_url: str | None = None,
        metadata_update: dict[str, Any] | None = None,
    ) -> AgentContentJob | None:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in CONTENT_JOB_STATUSES:
            raise ValueError(f"Unsupported content job status: {status}")

        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                if row is None:
                    return None

                row.status = normalized_status
                row.updated_at = _now_utc()

                if script_text is not None:
                    row.script_text = script_text
                if script_model is not None:
                    row.script_model = script_model
                if kling_task_id is not None:
                    row.kling_task_id = kling_task_id
                if video_url is not None:
                    row.video_url = video_url
                if youtube_video_id is not None:
                    row.youtube_video_id = youtube_video_id
                if youtube_video_url is not None:
                    row.youtube_video_url = youtube_video_url
                if normalized_status in {"published", "failed"} and row.finished_at is None:
                    row.finished_at = _now_utc()

                if metadata_update:
                    merged = {}
                    if row.metadata_json:
                        try:
                            parsed = json.loads(row.metadata_json)
                            if isinstance(parsed, dict):
                                merged = parsed
                        except Exception:
                            merged = {}
                    merged.update(metadata_update)
                    row.metadata_json = json.dumps(merged, ensure_ascii=False)

                await session.flush()
                return row

    async def mark_failed(self, *, job_id: int, error: str | None = None) -> AgentContentJob | None:
        now_utc = _now_utc()
        reason = str(error or "").strip()[:2000] or "content_job_failed"
        retryable = self._is_retryable_error(reason)

        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                if row is None:
                    return None

                row.retry_count = int(row.retry_count or 0) + 1
                row.last_error = reason
                row.updated_at = now_utc

                should_retry = retryable and row.retry_count < int(row.max_retries or 0)
                if should_retry:
                    delay_seconds = _compute_retry_delay_seconds(row.retry_count)
                    row.status = "planned"
                    row.started_at = None
                    row.scheduled_for = now_utc + timedelta(seconds=delay_seconds)
                else:
                    row.status = "failed"
                    row.finished_at = now_utc

                await session.flush()
                return row

    async def publish_rendered_job(self, *, job_id: int) -> AgentContentJob | None:
        """Publish rendered job to YouTube (worker integration point after `rendered`)."""
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                if row is None:
                    return None
                if row.status != "rendered":
                    raise RuntimeError(f"Content job {job_id} is not in rendered status")
                if not row.video_url:
                    raise RuntimeError(f"Content job {job_id} has empty video_url")
                agent = await session.scalar(select(Agent).where(Agent.id == row.agent_id))
                if agent is None:
                    raise RuntimeError(f"Agent not found for content job: {job_id}")
                yt_channel = await session.scalar(
                    select(AgentChannelConnection).where(
                        AgentChannelConnection.agent_id == agent.id,
                        AgentChannelConnection.provider == "youtube",
                        AgentChannelConnection.connection_type == "oauth",
                        AgentChannelConnection.is_active.is_(True),
                        AgentChannelConnection.encrypted_credentials.is_not(None),
                    )
                )
                if yt_channel is None or not yt_channel.encrypted_credentials:
                    raise RuntimeError("YouTube OAuth channel is not connected")
                try:
                    token_bundle = json.loads(decrypt_token(yt_channel.encrypted_credentials))
                    if not isinstance(token_bundle, dict):
                        token_bundle = {}
                except Exception:
                    raise RuntimeError("YouTube OAuth credentials bundle is invalid")

                cfg = parse_agent_template_config(agent.template_config)
                company_name = str(cfg.get("company_name") or "").strip() or "AI Content"
                content_meta = {}
                if row.metadata_json:
                    try:
                        parsed_meta = json.loads(row.metadata_json)
                        if isinstance(parsed_meta, dict):
                            content_meta = parsed_meta
                    except Exception:
                        content_meta = {}
                content_date = str(content_meta.get("content_date") or "").strip()
                title = f"{company_name} — Shorts"
                if content_date:
                    title = f"{company_name} — {content_date}"

                row.status = "publishing"
                row.updated_at = _now_utc()
                await session.flush()

        try:
            publish_result = await get_youtube_client().upload_short(
                token_bundle=token_bundle,
                video_url=str(row.video_url),
                title=title[:100],
                description="",
                privacy_status="public",
            )
            updated_bundle = publish_result.get("token_bundle") or token_bundle
            video_id = str(publish_result.get("video_id") or "").strip()
            video_page_url = str(publish_result.get("video_url") or "").strip()

            async with async_session_maker() as session:
                async with session.begin():
                    db_row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                    if db_row is None:
                        return None
                    db_row.status = "published"
                    db_row.youtube_video_id = video_id or None
                    db_row.youtube_video_url = video_page_url or None
                    db_row.finished_at = _now_utc()
                    db_row.updated_at = _now_utc()
                    await session.flush()

                    db_channel = await session.scalar(
                        select(AgentChannelConnection).where(
                            AgentChannelConnection.agent_id == db_row.agent_id,
                            AgentChannelConnection.provider == "youtube",
                            AgentChannelConnection.connection_type == "oauth",
                        )
                    )
                    if db_channel is not None:
                        db_channel.encrypted_credentials = encrypt_token(json.dumps(updated_bundle, ensure_ascii=False))
                        db_channel.updated_at = _now_utc()
                    return db_row
        except Exception as exc:
            await self.mark_failed(job_id=job_id, error=str(exc))
            return None

    @staticmethod
    def _is_retryable_error(error: str) -> bool:
        lower = (error or "").strip().lower()
        if not lower:
            return True
        if any(marker in lower for marker in FAIL_FAST_ERROR_MARKERS):
            return False
        if any(marker in lower for marker in RETRYABLE_ERROR_MARKERS):
            return True
        # Unknown errors default to retry to survive transient infrastructure issues.
        return True


_content_job_service: ContentJobService | None = None


def get_content_job_service() -> ContentJobService:
    global _content_job_service
    if _content_job_service is None:
        _content_job_service = ContentJobService()
    return _content_job_service
