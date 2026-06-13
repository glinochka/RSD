"""CRUD service for ArticlePublisher: settings, topics, images, jobs."""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc, func

from ...alembic.database import async_session_maker
from ...alembic.models import (
    ArticlePublisherImage,
    ArticlePublisherJob,
    ArticlePublisherSettings,
    ArticlePublisherTopic,
)

logger = logging.getLogger(__name__)

ARTICLE_PUBLISHER_JOB_STATUSES = {
    "pending", "generating", "publishing", "published", "failed",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_images_dir() -> str:
    base = os.environ.get("ARTICLE_PUBLISHER_IMAGES_DIR", "")
    if not base:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        base = os.path.join(backend_root, "app", "uploads", "article_publisher")
    os.makedirs(base, exist_ok=True)
    return base


class ArticlePublisherService:
    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_settings(self) -> ArticlePublisherSettings:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(ArticlePublisherSettings).limit(1))
                if row is None:
                    row = ArticlePublisherSettings()
                    session.add(row)
                    await session.flush()
                    await session.refresh(row)
                return row

    async def update_settings(self, updates: dict[str, Any]) -> ArticlePublisherSettings:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(ArticlePublisherSettings).limit(1))
                if row is None:
                    row = ArticlePublisherSettings()
                    session.add(row)

                allowed = {
                    "posting_enabled", "posting_frequency_hours",
                    "vcru_enabled", "vcru_email", "vcru_password_enc", "vcru_subsite_id",
                    "zen_enabled", "zen_login", "zen_password_enc", "zen_oauth_token_enc", "zen_channel_id",
                    "auto_topics_enabled", "topic_categories_json", "promo_ratio",
                    "company_name", "company_url", "company_description",
                    "article_min_words", "article_max_words",
                }
                for key, value in updates.items():
                    if key in allowed:
                        setattr(row, key, value)
                row.updated_at = _now_utc()
                await session.flush()
                await session.refresh(row)
                return row

    def serialize_settings(self, row: ArticlePublisherSettings) -> dict[str, Any]:
        try:
            categories = json.loads(row.topic_categories_json or "[]")
        except Exception:
            categories = []
        return {
            "id": row.id,
            "posting_enabled": row.posting_enabled,
            "posting_frequency_hours": row.posting_frequency_hours,
            "vcru_enabled": row.vcru_enabled,
            "vcru_email": row.vcru_email,
            "vcru_has_password": bool(row.vcru_password_enc),
            "vcru_subsite_id": row.vcru_subsite_id,
            "zen_enabled": row.zen_enabled,
            "zen_login": row.zen_login,
            "zen_has_password": bool(row.zen_password_enc),
            "zen_channel_id": row.zen_channel_id,
            "auto_topics_enabled": row.auto_topics_enabled,
            "topic_categories": categories,
            "promo_ratio": row.promo_ratio,
            "company_name": row.company_name,
            "company_url": row.company_url,
            "company_description": row.company_description,
            "article_min_words": row.article_min_words,
            "article_max_words": row.article_max_words,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    # ------------------------------------------------------------------
    # Topics
    # ------------------------------------------------------------------

    async def list_topics(
        self, *, page: int = 1, page_size: int = 50, unused_only: bool = False,
    ) -> tuple[list[ArticlePublisherTopic], int]:
        offset = (page - 1) * page_size
        async with async_session_maker() as session:
            async with session.begin():
                q = select(ArticlePublisherTopic)
                if unused_only:
                    q = q.where(ArticlePublisherTopic.used.is_(False))
                total = await session.scalar(
                    select(func.count()).select_from(q.subquery())
                ) or 0
                rows = (
                    await session.execute(
                        q.order_by(desc(ArticlePublisherTopic.created_at))
                        .offset(offset)
                        .limit(page_size)
                    )
                ).scalars().all()
                return list(rows), int(total)

    async def add_topics(self, topics: list[str], source: str = "manual") -> list[ArticlePublisherTopic]:
        now = _now_utc()
        added: list[ArticlePublisherTopic] = []
        async with async_session_maker() as session:
            async with session.begin():
                for text in topics:
                    text = text.strip()
                    if not text:
                        continue
                    row = ArticlePublisherTopic(topic=text, source=source, used=False, created_at=now)
                    session.add(row)
                    added.append(row)
                await session.flush()
                for row in added:
                    await session.refresh(row)
        return added

    async def delete_topic(self, topic_id: int) -> bool:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(ArticlePublisherTopic).where(ArticlePublisherTopic.id == topic_id)
                )
                if row is None:
                    return False
                await session.delete(row)
        return True

    async def pick_next_topic(self) -> str | None:
        """Return next unused topic text and mark it used."""
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(ArticlePublisherTopic)
                    .where(ArticlePublisherTopic.used.is_(False))
                    .order_by(ArticlePublisherTopic.created_at.asc())
                    .limit(1)
                )
                if row is None:
                    return None
                row.used = True
                await session.flush()
                return str(row.topic)

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    async def list_images(self) -> list[dict[str, Any]]:
        async with async_session_maker() as session:
            async with session.begin():
                rows = (
                    await session.execute(
                        select(ArticlePublisherImage).order_by(desc(ArticlePublisherImage.created_at))
                    )
                ).scalars().all()
        return [self._serialize_image(r) for r in rows]

    async def save_image(
        self,
        *,
        file_bytes: bytes,
        original_name: str,
        mime_type: str | None,
    ) -> dict[str, Any]:
        ext = os.path.splitext(original_name)[1] or ".jpg"
        storage_filename = f"{uuid.uuid4().hex}{ext}"
        images_dir = _get_images_dir()
        dest_path = os.path.join(images_dir, storage_filename)
        with open(dest_path, "wb") as fh:
            fh.write(file_bytes)

        async with async_session_maker() as session:
            async with session.begin():
                row = ArticlePublisherImage(
                    original_name=original_name[:512],
                    storage_filename=storage_filename,
                    mime_type=(mime_type or "")[:128] or None,
                    size_bytes=len(file_bytes),
                    created_at=_now_utc(),
                )
                session.add(row)
                await session.flush()
                await session.refresh(row)
        return self._serialize_image(row)

    async def delete_image(self, image_id: int) -> bool:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(ArticlePublisherImage).where(ArticlePublisherImage.id == image_id)
                )
                if row is None:
                    return False
                storage_filename = row.storage_filename
                await session.delete(row)

        try:
            path = os.path.join(_get_images_dir(), storage_filename)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            logger.warning("Failed to delete image file: %s", storage_filename)
        return True

    async def get_random_image_path(self) -> str | None:
        """Return filesystem path to a random image from the pool."""
        import random
        async with async_session_maker() as session:
            async with session.begin():
                rows = (
                    await session.execute(select(ArticlePublisherImage))
                ).scalars().all()
        if not rows:
            return None
        row = random.choice(rows)
        path = os.path.join(_get_images_dir(), row.storage_filename)
        return path if os.path.exists(path) else None

    def _serialize_image(self, row: ArticlePublisherImage) -> dict[str, Any]:
        return {
            "id": row.id,
            "original_name": row.original_name,
            "storage_filename": row.storage_filename,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "url": f"/api/admin/article-publisher/images/{row.id}/file",
        }

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    async def list_jobs(
        self, *, page: int = 1, page_size: int = 20,
    ) -> tuple[list[ArticlePublisherJob], int]:
        offset = (page - 1) * page_size
        async with async_session_maker() as session:
            async with session.begin():
                total = await session.scalar(
                    select(func.count(ArticlePublisherJob.id))
                ) or 0
                rows = (
                    await session.execute(
                        select(ArticlePublisherJob)
                        .order_by(desc(ArticlePublisherJob.created_at))
                        .offset(offset)
                        .limit(page_size)
                    )
                ).scalars().all()
                return list(rows), int(total)

    async def get_latest_job(self) -> ArticlePublisherJob | None:
        async with async_session_maker() as session:
            async with session.begin():
                return await session.scalar(
                    select(ArticlePublisherJob)
                    .order_by(desc(ArticlePublisherJob.created_at))
                    .limit(1)
                )

    async def has_published_between(self, *, start_utc: datetime, end_utc: datetime) -> bool:
        async with async_session_maker() as session:
            async with session.begin():
                found = await session.scalar(
                    select(ArticlePublisherJob.id)
                    .where(
                        ArticlePublisherJob.status == "published",
                        ArticlePublisherJob.finished_at.is_not(None),
                        ArticlePublisherJob.finished_at >= start_utc,
                        ArticlePublisherJob.finished_at < end_utc,
                    )
                    .limit(1)
                )
                return found is not None

    async def create_job(
        self,
        *,
        platform: str,
        topic: str,
        is_promo: bool,
        scheduled_for: datetime,
    ) -> ArticlePublisherJob:
        now = _now_utc()
        async with async_session_maker() as session:
            async with session.begin():
                row = ArticlePublisherJob(
                    status="pending",
                    platform=platform,
                    topic=topic,
                    is_promo=is_promo,
                    scheduled_for=scheduled_for,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return row

    async def mark_job_status(
        self,
        *,
        job_id: int,
        status: str,
        article_title: str | None = None,
        article_content: str | None = None,
        published_url: str | None = None,
        error: str | None = None,
    ) -> ArticlePublisherJob | None:
        now = _now_utc()
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(ArticlePublisherJob).where(ArticlePublisherJob.id == job_id)
                )
                if row is None:
                    return None
                row.status = status
                row.updated_at = now
                if article_title is not None:
                    row.article_title = article_title
                if article_content is not None:
                    row.article_content = article_content
                if published_url is not None:
                    row.published_url = published_url
                if error is not None:
                    row.last_error = str(error)[:2000]
                if status == "generating" and row.started_at is None:
                    row.started_at = now
                if status in {"published", "failed"} and row.finished_at is None:
                    row.finished_at = now
                await session.flush()
                await session.refresh(row)
                return row

    async def determine_next_is_promo(self, promo_ratio: int = 60) -> bool:
        """Use last 10 jobs to determine if next should be promo (60/40 rule)."""
        async with async_session_maker() as session:
            async with session.begin():
                recent = (
                    await session.execute(
                        select(ArticlePublisherJob)
                        .where(ArticlePublisherJob.status == "published")
                        .order_by(desc(ArticlePublisherJob.created_at))
                        .limit(10)
                    )
                ).scalars().all()
        if not recent:
            return True
        promo_count = sum(1 for j in recent if j.is_promo)
        current_ratio = int(promo_count / len(recent) * 100)
        return current_ratio < promo_ratio

    def serialize_job(self, row: ArticlePublisherJob) -> dict[str, Any]:
        return {
            "id": row.id,
            "status": row.status,
            "platform": row.platform,
            "topic": row.topic,
            "is_promo": row.is_promo,
            "article_title": row.article_title,
            "published_url": row.published_url,
            "last_error": row.last_error,
            "scheduled_for": row.scheduled_for.isoformat() if row.scheduled_for else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


_service: ArticlePublisherService | None = None


def get_article_publisher_service() -> ArticlePublisherService:
    global _service
    if _service is None:
        _service = ArticlePublisherService()
    return _service
