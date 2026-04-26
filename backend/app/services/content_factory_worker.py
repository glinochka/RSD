"""Autonomous background worker for content_factory pipeline."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentAnalyticsMessage, AgentContentJob
from ..config import settings
from .content_job_service import get_content_job_service
from .kling_client import get_kling_client
from .script_service import get_script_service

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ContentFactoryWorker:
    """Background worker: claim -> script -> Kling -> YouTube -> finalize."""

    def __init__(
        self,
        *,
        poll_interval_seconds: int | None = None,
        render_poll_interval_seconds: int | None = None,
        render_max_polls: int | None = None,
    ) -> None:
        self.poll_interval_seconds = max(3, int(poll_interval_seconds or settings.CONTENT_FACTORY_POLL_INTERVAL_SECONDS))
        self.render_poll_interval_seconds = max(
            2,
            int(render_poll_interval_seconds or settings.CONTENT_FACTORY_RENDER_POLL_INTERVAL_SECONDS),
        )
        self.render_max_polls = max(5, int(render_max_polls or settings.CONTENT_FACTORY_RENDER_MAX_POLLS))
        self._stop = asyncio.Event()

    async def shutdown(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        logger.info("ContentFactoryWorker starting")
        try:
            while not self._stop.is_set():
                try:
                    processed = await self.process_once()
                except Exception as exc:
                    logger.exception("ContentFactoryWorker loop error: %s", exc)
                    processed = False

                if processed:
                    await asyncio.sleep(0)
                    continue

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("ContentFactoryWorker cancelled")
            raise
        finally:
            logger.info("ContentFactoryWorker stopped")

    async def process_once(self) -> bool:
        """Single iteration for runtime and tests. Returns True if a job was processed."""
        service = get_content_job_service()
        await service.enqueue_daily_jobs(_now_utc())
        claimed = await service.claim_next_job(now=_now_utc())
        if claimed is None:
            return False
        await self._process_job(job_id=int(claimed.id))
        return True

    async def _process_job(self, *, job_id: int) -> None:
        service = get_content_job_service()
        logger.info("ContentFactoryWorker processing job_id=%s", job_id)

        try:
            script = await get_script_service().generate_for_job(job_id=job_id)
            await self._log_pipeline_event(job_id=job_id, event_name="script_generated", tool_status="success")
        except Exception as exc:
            await service.mark_failed(job_id=job_id, error=f"script_generation_failed: {exc}")
            return

        try:
            kling_model = await self._resolve_kling_model(job_id=job_id)
            await service.mark_status(
                job_id=job_id,
                status="rendering",
                metadata_update={"render_started_at": _now_utc().isoformat()},
            )
            kling_task_id = await get_kling_client().submit_render(
                script_text=script.script_text,
                duration_seconds=script.max_duration_seconds,
                model=kling_model,
            )
            await service.mark_status(
                job_id=job_id,
                status="rendering",
                kling_task_id=kling_task_id,
            )
            await self._log_pipeline_event(job_id=job_id, event_name="kling_submitted", tool_status="success")
        except Exception as exc:
            await service.mark_failed(job_id=job_id, error=f"kling_submit_failed: {exc}")
            return

        render_payload = None
        for attempt in range(1, self.render_max_polls + 1):
            try:
                render_payload = await get_kling_client().poll_render(task_id=kling_task_id)
            except Exception as exc:
                if attempt >= self.render_max_polls:
                    await service.mark_failed(job_id=job_id, error=f"kling_poll_failed: {exc}")
                    return
                await asyncio.sleep(self._render_backoff_delay(attempt))
                continue

            status = str(render_payload.get("status") or "rendering").strip().lower()
            if status == "rendered":
                video_url = str(render_payload.get("video_url") or "").strip()
                if not video_url:
                    await service.mark_failed(job_id=job_id, error="kling_render_missing_video_url")
                    return
                await service.mark_status(
                    job_id=job_id,
                    status="rendered",
                    video_url=video_url,
                    metadata_update={"render_finished_at": _now_utc().isoformat()},
                )
                await self._log_pipeline_event(job_id=job_id, event_name="kling_rendered", tool_status="success")
                break
            if status == "failed":
                await service.mark_failed(
                    job_id=job_id,
                    error=f"kling_render_failed: {render_payload.get('error') or 'unknown'}",
                )
                return

            if attempt >= self.render_max_polls:
                await service.mark_failed(job_id=job_id, error="kling_render_timeout")
                return
            await asyncio.sleep(self._render_backoff_delay(attempt))
        else:
            await service.mark_failed(job_id=job_id, error="kling_render_timeout")
            return

        published = await service.publish_rendered_job(job_id=job_id)
        if not published:
            await self._log_pipeline_event(
                job_id=job_id,
                event_name="publish_failed",
                tool_status="failed",
                error=await self._load_job_last_error(job_id=job_id),
            )
            logger.warning("ContentFactoryWorker publish step returned empty result job_id=%s", job_id)
            return
        await self._log_pipeline_event(job_id=job_id, event_name="youtube_published", tool_status="success")
        logger.info("ContentFactoryWorker finished job_id=%s final_status=%s", job_id, published.status)

    async def _resolve_kling_model(self, *, job_id: int) -> str:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                if row is None:
                    return "kling-v1"
                agent = await session.scalar(select(Agent).where(Agent.id == row.agent_id))
                if agent is None:
                    return "kling-v1"
                try:
                    import json

                    cfg = json.loads(agent.template_config or "{}")
                    if isinstance(cfg, dict):
                        model = str(cfg.get("kling_model") or "").strip()
                        if model:
                            return model
                except Exception:
                    pass
        return "kling-v1"

    def _render_backoff_delay(self, attempt: int) -> float:
        # 6, 9, 13.5 ... capped at 60 sec.
        base = float(self.render_poll_interval_seconds)
        delay = min(base * (1.5 ** max(0, attempt - 1)), 60.0)
        return delay

    async def _load_job_last_error(self, *, job_id: int) -> str:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                if not row:
                    return ""
                return str(row.last_error or "").strip()[:800]

    async def _log_pipeline_event(
        self,
        *,
        job_id: int,
        event_name: str,
        tool_status: str,
        error: str | None = None,
    ) -> None:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                    if row is None:
                        return
                    agent = await session.scalar(select(Agent).where(Agent.id == row.agent_id))
                    if agent is None:
                        return
                    analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
                    message_text = f"content_job_id={job_id} event={event_name}"
                    if error:
                        message_text = f"{message_text} error={str(error)[:500]}"
                    session.add(
                        AgentAnalyticsMessage(
                            agent_id=agent.id,
                            bot_id=analytics_namespace_id,
                            role="operator",
                            channel="dashboard",
                            user_external_id=None,
                            user_display_name=None,
                            telegram_peer_access_hash=None,
                            tool_name=event_name,
                            tool_args_hash=None,
                            tool_status=tool_status,
                            latency_ms=0,
                            crm_provider=None,
                            message_text=message_text,
                        )
                    )
        except Exception:
            logger.exception("Failed to log content_factory pipeline event: job_id=%s event=%s", job_id, event_name)


_content_factory_worker: ContentFactoryWorker | None = None


def get_content_factory_worker() -> ContentFactoryWorker:
    global _content_factory_worker
    if _content_factory_worker is None:
        _content_factory_worker = ContentFactoryWorker()
    return _content_factory_worker
