import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.alembic.models import Agent, AgentContentJob
from app.services.content_job_service import ContentJobService


class _MockAsyncContextManager:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.mark.asyncio
async def test_enqueue_daily_jobs_deduplicates_per_day(test_session, test_user, monkeypatch):
    service = ContentJobService()
    monkeypatch.setattr(
        "app.services.content_job_service.async_session_maker",
        lambda: _MockAsyncContextManager(test_session),
    )

    cfg = {
        "company_name": "Acme AI",
        "company_activity": "Контент-маркетинг",
        "content_language": "ru",
        "daily_posting_enabled": True,
        "daily_post_time": "10:00",
        "timezone": "UTC",
        "video_duration_seconds": 8,
        "kling_model": "kling-v1",
    }
    async with test_session.begin():
        test_session.add(
            Agent(
                user_id=test_user.id,
                bot_id=111111,
                bot_username="content_factory_bot",
                encrypted_token="mock_encrypted_token",
                template_type="content_factory",
                template_config=json.dumps(cfg, ensure_ascii=False),
                system_prompt="test",
                is_active=True,
            )
        )

    now = datetime(2026, 4, 27, 12, 0, 0)
    first = await service.enqueue_daily_jobs(now)
    second = await service.enqueue_daily_jobs(now)

    async with test_session.begin():
        rows = (await test_session.execute(select(AgentContentJob))).scalars().all()

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped_duplicates"] == 1
    assert len(rows) == 1
    assert rows[0].status == "planned"
    assert rows[0].scheduled_for == datetime(2026, 4, 27, 10, 0, 0)


@pytest.mark.asyncio
async def test_claim_next_job_marks_started_once(test_session, test_user, monkeypatch):
    service = ContentJobService()
    monkeypatch.setattr(
        "app.services.content_job_service.async_session_maker",
        lambda: _MockAsyncContextManager(test_session),
    )

    async with test_session.begin():
        test_session.add(
            Agent(
                user_id=test_user.id,
                bot_id=222222,
                bot_username="content_factory_bot_2",
                encrypted_token="mock_encrypted_token",
                template_type="content_factory",
                template_config=json.dumps({"company_name": "A", "company_activity": "B"}),
                system_prompt="test",
                is_active=True,
            )
        )
        await test_session.flush()
        agent = await test_session.scalar(select(Agent).where(Agent.bot_id == 222222))
        test_session.add(
            AgentContentJob(
                agent_id=agent.id,
                status="planned",
                scheduled_for=datetime(2026, 4, 27, 9, 0, 0),
                retry_count=0,
                max_retries=3,
                created_at=datetime(2026, 4, 27, 9, 0, 0),
                updated_at=datetime(2026, 4, 27, 9, 0, 0),
            )
        )

    claimed = await service.claim_next_job(now=datetime(2026, 4, 27, 12, 0, 0))
    claimed_again = await service.claim_next_job(now=datetime(2026, 4, 27, 12, 0, 0))

    assert claimed is not None
    assert claimed.started_at is not None
    assert claimed_again is None


@pytest.mark.asyncio
async def test_mark_failed_retries_transient_error(test_session, test_user, monkeypatch):
    service = ContentJobService()
    monkeypatch.setattr(
        "app.services.content_job_service.async_session_maker",
        lambda: _MockAsyncContextManager(test_session),
    )

    async with test_session.begin():
        test_session.add(
            Agent(
                user_id=test_user.id,
                bot_id=333333,
                bot_username="content_factory_bot_3",
                encrypted_token="mock_encrypted_token",
                template_type="content_factory",
                template_config=json.dumps({"company_name": "A", "company_activity": "B"}),
                system_prompt="test",
                is_active=True,
            )
        )
        await test_session.flush()
        agent = await test_session.scalar(select(Agent).where(Agent.bot_id == 333333))
        job = AgentContentJob(
            agent_id=agent.id,
            status="planned",
            scheduled_for=datetime(2026, 4, 20, 9, 0, 0),
            retry_count=0,
            max_retries=3,
            created_at=datetime(2026, 4, 27, 9, 0, 0),
            updated_at=datetime(2026, 4, 27, 9, 0, 0),
        )
        test_session.add(job)
        await test_session.flush()
        job_id = job.id

    row = await service.mark_failed(job_id=job_id, error="Temporary network timeout")

    assert row is not None
    assert row.status == "planned"
    assert row.retry_count == 1
    assert row.scheduled_for > datetime(2026, 4, 20, 9, 0, 0)
    assert row.started_at is None


@pytest.mark.asyncio
async def test_mark_failed_fail_fast_on_auth_config_errors(test_session, test_user, monkeypatch):
    service = ContentJobService()
    monkeypatch.setattr(
        "app.services.content_job_service.async_session_maker",
        lambda: _MockAsyncContextManager(test_session),
    )

    async with test_session.begin():
        test_session.add(
            Agent(
                user_id=test_user.id,
                bot_id=444444,
                bot_username="content_factory_bot_4",
                encrypted_token="mock_encrypted_token",
                template_type="content_factory",
                template_config=json.dumps({"company_name": "A", "company_activity": "B"}),
                system_prompt="test",
                is_active=True,
            )
        )
        await test_session.flush()
        agent = await test_session.scalar(select(Agent).where(Agent.bot_id == 444444))
        job = AgentContentJob(
            agent_id=agent.id,
            status="planned",
            scheduled_for=datetime(2026, 4, 27, 9, 0, 0),
            retry_count=0,
            max_retries=3,
            created_at=datetime(2026, 4, 27, 9, 0, 0),
            updated_at=datetime(2026, 4, 27, 9, 0, 0),
        )
        test_session.add(job)
        await test_session.flush()
        job_id = job.id

    row = await service.mark_failed(job_id=job_id, error="OAuth token invalid")

    assert row is not None
    assert row.status == "failed"
    assert row.retry_count == 1
    assert row.finished_at is not None


@pytest.mark.asyncio
async def test_mark_status_updates_payload_fields(test_session, test_user, monkeypatch):
    service = ContentJobService()
    monkeypatch.setattr(
        "app.services.content_job_service.async_session_maker",
        lambda: _MockAsyncContextManager(test_session),
    )

    async with test_session.begin():
        test_session.add(
            Agent(
                user_id=test_user.id,
                bot_id=555555,
                bot_username="content_factory_bot_5",
                encrypted_token="mock_encrypted_token",
                template_type="content_factory",
                template_config=json.dumps({"company_name": "A", "company_activity": "B"}),
                system_prompt="test",
                is_active=True,
            )
        )
        await test_session.flush()
        agent = await test_session.scalar(select(Agent).where(Agent.bot_id == 555555))
        job = AgentContentJob(
            agent_id=agent.id,
            status="planned",
            scheduled_for=datetime(2026, 4, 27, 9, 0, 0),
            retry_count=0,
            max_retries=3,
            created_at=datetime(2026, 4, 27, 9, 0, 0),
            updated_at=datetime(2026, 4, 27, 9, 0, 0),
        )
        test_session.add(job)
        await test_session.flush()
        job_id = job.id

    row = await service.mark_status(
        job_id=job_id,
        status="script_ready",
        script_text="8-second script",
        script_model="deepseek-chat",
        metadata_update={"provider": "youtube"},
    )

    assert row is not None
    assert row.status == "script_ready"
    assert row.script_text == "8-second script"
    assert row.script_model == "deepseek-chat"
    assert row.metadata_json is not None
    payload = json.loads(row.metadata_json)
    assert payload.get("provider") == "youtube"
