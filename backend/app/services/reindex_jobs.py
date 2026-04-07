from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from logging import getLogger

from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, ReindexJob
from ..config import settings
from ..qdrant.embeddings import get_active_embedding_profile
from ..qdrant.indexer import reindex_document_from_existing_chunks
from ..router_documents.dao import DocumentDAO, ReindexJobDAO

logger = getLogger(__name__)

REINDEX_POLL_INTERVAL_SECONDS = 5
REINDEX_ALLOWED_ACTIVE_STATUSES = {"queued", "retrying", "running"}
REINDEX_MAX_BACKOFF_SECONDS = 60


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_transient_database_error(exc: Exception) -> bool:
    transient_tokens = (
        "connection was closed",
        "connection reset",
        "connection refused",
        "server closed the connection",
        "terminating connection",
        "could not connect",
    )
    asyncpg_transient_names = {
        "ConnectionDoesNotExistError",
        "ConnectionFailureError",
        "ConnectionResetError",
        "CannotConnectNowError",
        "TooManyConnectionsError",
    }

    current: BaseException | None = exc
    depth = 0
    while current is not None and depth < 8:
        if isinstance(current, (DBAPIError, OperationalError, InterfaceError, ConnectionError, OSError, TimeoutError)):
            return True

        current_type = type(current)
        if current_type.__module__.startswith("asyncpg") and current_type.__name__ in asyncpg_transient_names:
            return True

        message = str(current).lower()
        if any(token in message for token in transient_tokens):
            return True

        current = current.__cause__ or current.__context__
        depth += 1

    return False


def serialize_reindex_job(job: ReindexJob) -> dict:
    return {
        "id": job.id,
        "agent_id": job.agent_id,
        "status": job.status,
        "target_embedding_profile_key": job.target_embedding_profile_key,
        "target_embedding_schema_version": job.target_embedding_schema_version,
        "target_embedding_model_name": job.target_embedding_model_name,
        "batch_size": job.batch_size,
        "total_documents": job.total_documents,
        "processed_documents": job.processed_documents,
        "success_documents": job.success_documents,
        "failed_documents": job.failed_documents,
        "document_cursor": job.document_cursor,
        "last_error": job.last_error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


async def create_reindex_job(
    *,
    agent_pk: int,
    requested_by_user_id: int | None,
    batch_size: int,
    target_embedding_profile_key: str | None = None,
) -> ReindexJob:
    active_profile = get_active_embedding_profile()
    target_profile_key = target_embedding_profile_key or active_profile["profile_key"]
    if target_profile_key != active_profile["profile_key"]:
        raise ValueError("Only active embedding profile can be reindexed in current runtime")

    async with async_session_maker() as session:
        job_dao = ReindexJobDAO(session)
        doc_dao = DocumentDAO(session)
        async with session.begin():
            total_docs = await doc_dao.count_ready_for_reindex(agent_pk, target_profile_key)
            job = await job_dao.add(
                {
                    "agent_id": agent_pk,
                    "requested_by_user_id": requested_by_user_id,
                    "status": "queued",
                    "target_embedding_profile_key": target_profile_key,
                    "target_embedding_schema_version": active_profile["schema_version"],
                    "target_embedding_model_name": active_profile["model_name"],
                    "batch_size": batch_size,
                    "total_documents": total_docs,
                }
            )
            await session.flush()
            return job


async def list_reindex_jobs_for_agent(agent_pk: int) -> list[dict]:
    async with async_session_maker() as session:
        job_dao = ReindexJobDAO(session)
        async with session.begin():
            jobs = await job_dao.list_by_agent(agent_pk)
            return [serialize_reindex_job(j) for j in jobs]


async def cancel_reindex_job(job_id: int) -> ReindexJob | None:
    async with async_session_maker() as session:
        job_dao = ReindexJobDAO(session)
        async with session.begin():
            job = await job_dao.find_one_by_filter(id=job_id)
            if not job:
                return None
            if job.status in REINDEX_ALLOWED_ACTIVE_STATUSES:
                await job_dao.update(
                    job,
                    {
                        "status": "cancelled",
                        "finished_at": _utc_now_naive(),
                    },
                )
            return job


async def retry_reindex_job(job_id: int) -> ReindexJob | None:
    async with async_session_maker() as session:
        job_dao = ReindexJobDAO(session)
        doc_dao = DocumentDAO(session)
        async with session.begin():
            job = await job_dao.find_one_by_filter(id=job_id)
            if not job:
                return None
            if job.status not in {"failed", "cancelled", "completed"}:
                return job

            total_docs = await doc_dao.count_ready_for_reindex(job.agent_id, job.target_embedding_profile_key)
            await job_dao.update(
                job,
                {
                    "status": "retrying",
                    "document_cursor": 0,
                    "processed_documents": 0,
                    "success_documents": 0,
                    "failed_documents": 0,
                    "total_documents": total_docs,
                    "last_error": None,
                    "started_at": None,
                    "finished_at": None,
                },
            )
            return job


async def _process_single_job(job_id: int) -> None:
    while True:
        async with async_session_maker() as session:
            job_dao = ReindexJobDAO(session)
            doc_dao = DocumentDAO(session)
            async with session.begin():
                job = await job_dao.find_one_by_filter(id=job_id)
                if not job:
                    return
                if job.status == "cancelled":
                    if not job.finished_at:
                        await job_dao.update(job, {"finished_at": _utc_now_naive()})
                    return
                if job.status not in {"running", "retrying", "queued"}:
                    return
                if job.started_at is None:
                    await job_dao.update(job, {"started_at": _utc_now_naive(), "status": "running"})

                agent = await session.get(Agent, job.agent_id)
                if not agent or not agent.bot_id:
                    await job_dao.update(
                        job,
                        {
                            "status": "failed",
                            "last_error": "Agent not found or bot_id is missing",
                            "finished_at": _utc_now_naive(),
                        },
                    )
                    return

                batch = await doc_dao.list_ready_for_reindex_batch(
                    agent_pk=job.agent_id,
                    target_profile_key=job.target_embedding_profile_key,
                    cursor=job.document_cursor,
                    limit=job.batch_size,
                )
                if not batch:
                    await job_dao.update(
                        job,
                        {
                            "status": "completed",
                            "finished_at": _utc_now_naive(),
                        },
                    )
                    return

                for doc in batch:
                    try:
                        await reindex_document_from_existing_chunks(
                            agent_runtime_id=int(agent.bot_id),
                            document_id=doc.id,
                            source_profile_key=doc.embedding_profile_key,
                        )
                        await doc_dao.update(
                            doc,
                            {
                                "embedding_profile_key": job.target_embedding_profile_key,
                                "embedding_schema_version": job.target_embedding_schema_version,
                                "embedding_model_name": job.target_embedding_model_name,
                                "chunk_size": settings.EMBEDDING_CHUNK_SIZE,
                                "chunk_overlap": settings.EMBEDDING_CHUNK_OVERLAP,
                            },
                        )
                        await job_dao.update(
                            job,
                            {
                                "success_documents": job.success_documents + 1,
                            },
                        )
                        job.success_documents += 1
                    except Exception as exc:
                        error_text = str(exc)[:1000]
                        await job_dao.update(
                            job,
                            {
                                "failed_documents": job.failed_documents + 1,
                                "last_error": error_text,
                            },
                        )
                        job.failed_documents += 1
                    finally:
                        await job_dao.update(
                            job,
                            {
                                "processed_documents": job.processed_documents + 1,
                                "document_cursor": doc.id,
                            },
                        )
                        job.processed_documents += 1
                        job.document_cursor = doc.id
        await asyncio.sleep(0)


async def run_reindex_worker_forever() -> None:
    consecutive_db_failures = 0
    while True:
        try:
            job_id: int | None = None
            async with async_session_maker() as session:
                job_dao = ReindexJobDAO(session)
                async with session.begin():
                    job = await job_dao.claim_next_pending()
                    if job:
                        await job_dao.update(job, {"status": "running"})
                        job_id = job.id

            if not job_id:
                consecutive_db_failures = 0
                await asyncio.sleep(REINDEX_POLL_INTERVAL_SECONDS)
                continue

            await _process_single_job(job_id)
            consecutive_db_failures = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if _is_transient_database_error(exc):
                consecutive_db_failures += 1
                delay = min(
                    REINDEX_MAX_BACKOFF_SECONDS,
                    REINDEX_POLL_INTERVAL_SECONDS * (2 ** min(consecutive_db_failures, 5)),
                )
                logger.warning(
                    "Reindex worker: temporary DB failure (%s). Retrying in %s seconds.",
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            logger.exception("Reindex worker loop failed")
            await asyncio.sleep(REINDEX_POLL_INTERVAL_SECONDS)

