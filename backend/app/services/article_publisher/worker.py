"""Background worker for the article publisher pipeline."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .content_generator import generate_article
from .publishers.base import PublishResult
from .service import get_article_publisher_service
from .topic_generator import fetch_topics_from_search
from ...utils.crypto import decrypt_token

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _decrypt_safe(enc: str | None) -> str:
    if not enc:
        return ""
    try:
        return decrypt_token(enc)
    except Exception:
        return ""


class ArticlePublisherWorker:
    """Scheduled loop: generate topics → generate article → publish."""

    def __init__(self, poll_interval_seconds: int = 300) -> None:
        self.poll_interval_seconds = max(60, poll_interval_seconds)
        self._stop = asyncio.Event()
        self._local_tz = _resolve_publish_timezone()

    async def shutdown(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        logger.info("ArticlePublisherWorker starting")
        try:
            while not self._stop.is_set():
                try:
                    await self._tick()
                except Exception as exc:
                    logger.exception("ArticlePublisherWorker tick error: %s", exc)
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_interval_seconds
                    )
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("ArticlePublisherWorker cancelled")
            raise
        finally:
            logger.info("ArticlePublisherWorker stopped")

    async def _tick(self) -> None:
        service = get_article_publisher_service()
        settings = await service.get_settings()

        if not settings.posting_enabled:
            return

        active_platforms = []
        if settings.vcru_enabled and settings.vcru_email and settings.vcru_password_enc:
            active_platforms.append("vcru")
        if settings.zen_enabled and settings.zen_login and settings.zen_password_enc:
            active_platforms.append("yandex_zen")

        if not active_platforms:
            return

        if not await self._is_time_to_post_daily_window(settings):
            return

        platform = random.choice(active_platforms)
        topic = await self._resolve_topic(service, settings)
        if not topic:
            logger.warning("ArticlePublisherWorker: no topics available, skipping")
            return

        is_promo = await service.determine_next_is_promo(settings.promo_ratio)
        job = await service.create_job(
            platform=platform,
            topic=topic,
            is_promo=is_promo,
            scheduled_for=_now_utc(),
        )

        await self._process_job(job_id=job.id, settings=settings, platform=platform)

    async def _is_time_to_post_daily_window(self, settings) -> bool:
        """One post per day at deterministic random time in [08:00, 22:59] local."""
        service = get_article_publisher_service()
        latest = await service.get_latest_job()
        if latest and latest.status in ("pending", "generating", "publishing"):
            return False

        now_utc = _now_utc()
        now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(self._local_tz)
        today = now_local.date()

        if await service.has_published_between(
            start_utc=self._local_day_start_utc(today),
            end_utc=self._local_day_start_utc(today + timedelta(days=1)),
        ):
            return False

        target_local = self._daily_random_local_datetime(today=today, settings=settings)
        target_utc = target_local.astimezone(timezone.utc).replace(tzinfo=None)
        return now_utc >= target_utc

    def _daily_random_local_datetime(self, *, today: date, settings) -> datetime:
        seed_raw = (
            f"{today.isoformat()}|{settings.id}|{settings.company_name}|"
            f"{settings.vcru_email}|{settings.zen_login}"
        )
        seed = int(hashlib.sha256(seed_raw.encode("utf-8")).hexdigest()[:12], 16)
        rng = random.Random(seed)
        hour = rng.randint(8, 22)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        return datetime.combine(today, time(hour=hour, minute=minute, second=second), tzinfo=self._local_tz)

    def _local_day_start_utc(self, day: date) -> datetime:
        local_start = datetime.combine(day, time.min, tzinfo=self._local_tz)
        return local_start.astimezone(timezone.utc).replace(tzinfo=None)

    async def _resolve_topic(self, service, settings) -> str | None:
        topic = await service.pick_next_topic()
        if topic:
            return topic

        if settings.auto_topics_enabled:
            try:
                cats = json.loads(settings.topic_categories_json or "[]")
                if not isinstance(cats, list) or not cats:
                    cats = ["ИИ", "IT", "Автоматизация"]
                new_topics = await fetch_topics_from_search(cats, count=10)
                if new_topics:
                    await service.add_topics(new_topics, source="auto")
                    return await service.pick_next_topic()
            except Exception as exc:
                logger.warning("Auto topic generation failed: %s", exc)
        return None

    async def _process_job(self, *, job_id: int, settings, platform: str) -> None:
        service = get_article_publisher_service()
        await service.mark_job_status(job_id=job_id, status="generating")

        job_row = None
        try:
            jobs, _ = await service.list_jobs(page=1, page_size=100)
            job_row = next((j for j in jobs if j.id == job_id), None)
            if not job_row:
                return
        except Exception:
            return

        try:
            article = await generate_article(
                topic=job_row.topic,
                is_promo=job_row.is_promo,
                company_name=settings.company_name or "RSD AI",
                company_url=settings.company_url or "",
                company_description=settings.company_description or "",
                min_words=settings.article_min_words,
                max_words=settings.article_max_words,
                platform=platform,
            )
        except Exception as exc:
            await service.mark_job_status(job_id=job_id, status="failed", error=str(exc))
            return

        await service.mark_job_status(
            job_id=job_id,
            status="publishing",
            article_title=article.title,
            article_content=article.content[:10000],
        )

        image_path = await service.get_random_image_path()
        result = await self._publish(
            platform=platform,
            settings=settings,
            title=article.title,
            html_content=article.content,
            image_path=image_path,
        )

        if result.success:
            await service.mark_job_status(
                job_id=job_id,
                status="published",
                published_url=result.url,
            )
            logger.info(
                "ArticlePublisherWorker: published job_id=%d platform=%s url=%s",
                job_id, platform, result.url,
            )
        else:
            await service.mark_job_status(
                job_id=job_id,
                status="failed",
                error=result.error or "publish_failed",
            )

    async def _publish(
        self,
        *,
        platform: str,
        settings,
        title: str,
        html_content: str,
        image_path: str | None,
    ) -> PublishResult:
        from .publishers.base import PublishResult as PR
        try:
            if platform == "vcru":
                from .publishers.vcru import VcRuPublisher
                password = _decrypt_safe(settings.vcru_password_enc)
                publisher = VcRuPublisher(
                    email=settings.vcru_email,
                    password=password,
                    subsite_id=settings.vcru_subsite_id,
                )
            else:
                from .publishers.yandex_zen import YandexZenPublisher
                zen_password = _decrypt_safe(settings.zen_password_enc)
                publisher = YandexZenPublisher(
                    login=settings.zen_login,
                    password=zen_password,
                    channel_id=settings.zen_channel_id,
                )
            return await publisher.publish(
                title=title,
                html_content=html_content,
                image_path=image_path,
            )
        except Exception as exc:
            logger.exception("_publish failed platform=%s: %s", platform, exc)
            return PR(success=False, error=str(exc)[:500])


_worker: ArticlePublisherWorker | None = None


def get_article_publisher_worker() -> ArticlePublisherWorker:
    global _worker
    if _worker is None:
        _worker = ArticlePublisherWorker(poll_interval_seconds=300)
    return _worker


def _resolve_publish_timezone() -> ZoneInfo:
    timezone_name = (
        os.environ.get("ARTICLE_PUBLISHER_TIMEZONE", "").strip() or "Europe/Moscow"
    )
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        logger.warning("Invalid ARTICLE_PUBLISHER_TIMEZONE=%s; fallback to UTC", timezone_name)
        return ZoneInfo("UTC")
