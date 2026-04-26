import json
from types import SimpleNamespace
from datetime import datetime

import pytest
from sqlalchemy import select

from app.alembic.models import Agent, AgentContentJob
from app.services.script_service import ScriptService


class _MockAsyncContextManager:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def _completion(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                )
            )
        ]
    )


@pytest.mark.asyncio
async def test_generate_for_job_saves_script_and_metadata(test_session, test_user, monkeypatch):
    service = ScriptService()
    mock_session_maker = lambda: _MockAsyncContextManager(test_session)
    monkeypatch.setattr("app.services.script_service.async_session_maker", mock_session_maker)
    monkeypatch.setattr("app.services.content_job_service.async_session_maker", mock_session_maker)

    async def fake_create(**kwargs):
        return _completion(
            "# Сцена 1: *Короткий* хук про продукт.\n"
            "Покажи ценность за 8 секунд.\n\n"
            "Сцена 2: эту часть нужно удалить."
        )

    monkeypatch.setattr("app.services.script_service.ai_client.chat.completions.create", fake_create)

    cfg = {
        "company_name": "RSD AI",
        "company_activity": "AI-автоматизация коммуникаций",
        "brand_tone": "экспертный и дружелюбный",
        "content_language": "ru",
        "video_duration_seconds": 8,
    }
    async with test_session.begin():
        agent = Agent(
            user_id=test_user.id,
            bot_id=818181,
            bot_username="script_test_bot",
            encrypted_token="mock_encrypted_token",
            template_type="content_factory",
            template_config=json.dumps(cfg, ensure_ascii=False),
            system_prompt="Ты контент-агент",
            is_active=True,
        )
        test_session.add(agent)
        await test_session.flush()
        job = AgentContentJob(
            agent_id=agent.id,
            status="planned",
            scheduled_for=datetime(2026, 4, 27, 10, 0, 0),
            retry_count=0,
            max_retries=3,
            created_at=datetime(2026, 4, 27, 10, 0, 0),
            updated_at=datetime(2026, 4, 27, 10, 0, 0),
        )
        test_session.add(job)
        await test_session.flush()
        job_id = job.id

    result = await service.generate_for_job(job_id=job_id)
    assert "Сцена 2" not in result.script_text
    assert "#" not in result.script_text
    assert "*" not in result.script_text
    assert result.script_model == "deepseek-chat"

    async with test_session.begin():
        saved = await test_session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
    assert saved is not None
    assert saved.status == "script_ready"
    assert saved.script_text == result.script_text
    meta = json.loads(saved.metadata_json or "{}")
    assert meta.get("script_generation", {}).get("single_clip_enforced") is True


@pytest.mark.asyncio
async def test_generate_for_job_enforces_duration_limit(test_session, test_user, monkeypatch):
    service = ScriptService()
    mock_session_maker = lambda: _MockAsyncContextManager(test_session)
    monkeypatch.setattr("app.services.script_service.async_session_maker", mock_session_maker)
    monkeypatch.setattr("app.services.content_job_service.async_session_maker", mock_session_maker)

    async def fake_create(**kwargs):
        return _completion(
            "Это очень длинный сценарий который точно не помещается в заданный лимит "
            "и должен быть аккуратно обрезан по количеству слов для короткого видео"
        )

    monkeypatch.setattr("app.services.script_service.ai_client.chat.completions.create", fake_create)

    cfg = {
        "company_name": "RSD AI",
        "company_activity": "AI-автоматизация коммуникаций",
        "content_language": "ru",
        "video_duration_seconds": 3,
    }
    async with test_session.begin():
        agent = Agent(
            user_id=test_user.id,
            bot_id=919191,
            bot_username="script_test_bot_short",
            encrypted_token="mock_encrypted_token",
            template_type="content_factory",
            template_config=json.dumps(cfg, ensure_ascii=False),
            system_prompt="Ты контент-агент",
            is_active=True,
        )
        test_session.add(agent)
        await test_session.flush()
        job = AgentContentJob(
            agent_id=agent.id,
            status="planned",
            scheduled_for=datetime(2026, 4, 27, 10, 0, 0),
            retry_count=0,
            max_retries=3,
            created_at=datetime(2026, 4, 27, 10, 0, 0),
            updated_at=datetime(2026, 4, 27, 10, 0, 0),
        )
        test_session.add(job)
        await test_session.flush()
        job_id = job.id

    result = await service.generate_for_job(job_id=job_id)
    assert result.max_duration_seconds == 3
    assert result.trimmed_to_fit_duration is True
    assert len(result.script_text.split()) <= int(3 * 2.4)


@pytest.mark.asyncio
async def test_generate_for_missing_job_raises(monkeypatch, test_session):
    service = ScriptService()
    mock_session_maker = lambda: _MockAsyncContextManager(test_session)
    monkeypatch.setattr("app.services.script_service.async_session_maker", mock_session_maker)

    with pytest.raises(ValueError):
        await service.generate_for_job(job_id=999999)
