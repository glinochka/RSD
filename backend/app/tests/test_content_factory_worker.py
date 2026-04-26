from types import SimpleNamespace

import pytest

from app.services.content_factory_worker import ContentFactoryWorker


class _FakeContentJobService:
    def __init__(self):
        self.enqueue_calls = []
        self.claim_calls = 0
        self.mark_status_calls = []
        self.mark_failed_calls = []
        self.publish_calls = []
        self._claimed_job = SimpleNamespace(id=101)

    async def enqueue_daily_jobs(self, now):
        self.enqueue_calls.append(now)
        return {"created": 0, "skipped_duplicates": 0}

    async def claim_next_job(self, now=None):
        self.claim_calls += 1
        if self._claimed_job is None:
            return None
        job = self._claimed_job
        self._claimed_job = None
        return job

    async def mark_status(self, **kwargs):
        self.mark_status_calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    async def mark_failed(self, **kwargs):
        self.mark_failed_calls.append(kwargs)
        return SimpleNamespace(status="failed")

    async def publish_rendered_job(self, *, job_id: int):
        self.publish_calls.append(job_id)
        return SimpleNamespace(id=job_id, status="published")


class _FakeScriptService:
    def __init__(self, raise_error: bool = False):
        self.raise_error = raise_error
        self.calls = []

    async def generate_for_job(self, *, job_id: int):
        self.calls.append(job_id)
        if self.raise_error:
            raise RuntimeError("script exploded")
        return SimpleNamespace(
            script_text="short script",
            max_duration_seconds=8,
            script_model="deepseek-chat",
        )


class _FakeKlingClient:
    def __init__(self, fail_submit: bool = False):
        self.fail_submit = fail_submit
        self.submit_calls = []
        self.poll_calls = []
        self._poll_step = 0

    async def submit_render(self, **kwargs):
        self.submit_calls.append(kwargs)
        if self.fail_submit:
            raise RuntimeError("submit failed")
        return "kling-task-1"

    async def poll_render(self, *, task_id: str):
        self.poll_calls.append(task_id)
        self._poll_step += 1
        if self._poll_step == 1:
            return {"status": "rendering", "video_url": None, "error": None}
        return {"status": "rendered", "video_url": "https://cdn/video.mp4", "error": None}


@pytest.mark.asyncio
async def test_content_factory_worker_process_once_happy_path(monkeypatch):
    worker = ContentFactoryWorker(poll_interval_seconds=5, render_poll_interval_seconds=1, render_max_polls=5)
    fake_jobs = _FakeContentJobService()
    fake_script = _FakeScriptService()
    fake_kling = _FakeKlingClient()

    monkeypatch.setattr("app.services.content_factory_worker.get_content_job_service", lambda: fake_jobs)
    monkeypatch.setattr("app.services.content_factory_worker.get_script_service", lambda: fake_script)
    monkeypatch.setattr("app.services.content_factory_worker.get_kling_client", lambda: fake_kling)
    event_calls = []

    async def _fake_log_event(**kwargs):
        event_calls.append(kwargs)

    async def _fake_resolve_kling_model(*, job_id: int) -> str:
        return "kling-v1"

    monkeypatch.setattr(worker, "_resolve_kling_model", _fake_resolve_kling_model)
    monkeypatch.setattr(worker, "_log_pipeline_event", _fake_log_event)

    processed = await worker.process_once()

    assert processed is True
    assert fake_script.calls == [101]
    assert fake_kling.submit_calls
    assert fake_kling.poll_calls
    assert fake_jobs.publish_calls == [101]
    statuses = [item.get("status") for item in fake_jobs.mark_status_calls]
    assert statuses.count("rendering") >= 1
    assert "rendered" in statuses
    assert not fake_jobs.mark_failed_calls
    event_names = [item.get("event_name") for item in event_calls]
    assert "script_generated" in event_names
    assert "kling_submitted" in event_names
    assert "kling_rendered" in event_names
    assert "youtube_published" in event_names


@pytest.mark.asyncio
async def test_content_factory_worker_marks_failed_on_script_error(monkeypatch):
    worker = ContentFactoryWorker(poll_interval_seconds=5, render_poll_interval_seconds=1, render_max_polls=5)
    fake_jobs = _FakeContentJobService()
    fake_script = _FakeScriptService(raise_error=True)
    fake_kling = _FakeKlingClient()

    monkeypatch.setattr("app.services.content_factory_worker.get_content_job_service", lambda: fake_jobs)
    monkeypatch.setattr("app.services.content_factory_worker.get_script_service", lambda: fake_script)
    monkeypatch.setattr("app.services.content_factory_worker.get_kling_client", lambda: fake_kling)

    processed = await worker.process_once()

    assert processed is True
    assert fake_jobs.mark_failed_calls
    assert "script_generation_failed" in fake_jobs.mark_failed_calls[0]["error"]
    assert not fake_jobs.publish_calls


@pytest.mark.asyncio
async def test_content_factory_worker_process_once_without_jobs(monkeypatch):
    worker = ContentFactoryWorker(poll_interval_seconds=5, render_poll_interval_seconds=1, render_max_polls=5)
    fake_jobs = _FakeContentJobService()
    fake_jobs._claimed_job = None

    monkeypatch.setattr("app.services.content_factory_worker.get_content_job_service", lambda: fake_jobs)
    monkeypatch.setattr("app.services.content_factory_worker.get_script_service", lambda: _FakeScriptService())
    monkeypatch.setattr("app.services.content_factory_worker.get_kling_client", lambda: _FakeKlingClient())

    processed = await worker.process_once()

    assert processed is False
    assert fake_jobs.claim_calls == 1
