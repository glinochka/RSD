from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.kling_client import KlingClient, _SUBMIT_IDEMPOTENCY_CACHE


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict[str, Any] | list[Any] | None = None
    text: str = ""

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def content(self) -> bytes:
        return b"" if self.payload is None else b"1"

    def json(self) -> Any:
        return self.payload if self.payload is not None else {}


class _FakeAsyncClient:
    def __init__(self, *, responses: list[_FakeResponse], calls: list[dict[str, Any]], **kwargs):
        self._responses = responses
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def request(self, method: str, url: str, headers: dict[str, str] | None = None, json: Any = None):
        self._calls.append({"method": method, "url": url, "headers": headers or {}, "json": json})
        if not self._responses:
            raise RuntimeError("No prepared fake responses left")
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_submit_render_retries_and_returns_task(monkeypatch):
    _SUBMIT_IDEMPOTENCY_CACHE.clear()
    calls: list[dict[str, Any]] = []
    responses = [
        _FakeResponse(status_code=503, text="temporary upstream error"),
        _FakeResponse(status_code=200, payload={"task_id": "task_123"}),
    ]

    def fake_client_factory(*args, **kwargs):
        return _FakeAsyncClient(responses=responses, calls=calls, **kwargs)

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr("app.services.kling_client.httpx.AsyncClient", fake_client_factory)
    monkeypatch.setattr("app.services.kling_client.asyncio.sleep", fake_sleep)

    client = KlingClient(api_key="kling-secret", base_url="https://kling.example", max_retries=3)
    task_id = await client.submit_render(script_text="short script", duration_seconds=8, model="kling-v1")

    assert task_id == "task_123"
    assert len(calls) == 2
    assert sleep_calls == [0.5]


@pytest.mark.asyncio
async def test_submit_render_idempotency_replay_skips_second_request(monkeypatch):
    _SUBMIT_IDEMPOTENCY_CACHE.clear()
    calls: list[dict[str, Any]] = []
    responses = [_FakeResponse(status_code=200, payload={"task_id": "task_cached"})]

    def fake_client_factory(*args, **kwargs):
        return _FakeAsyncClient(responses=responses, calls=calls, **kwargs)

    monkeypatch.setattr("app.services.kling_client.httpx.AsyncClient", fake_client_factory)

    client = KlingClient(api_key="kling-secret", base_url="https://kling.example")
    key = "fixed-idempotency-key"

    first = await client.submit_render(
        script_text="one script",
        duration_seconds=8,
        model="kling-v1",
        idempotency_key=key,
    )
    second = await client.submit_render(
        script_text="one script",
        duration_seconds=8,
        model="kling-v1",
        idempotency_key=key,
    )

    assert first == "task_cached"
    assert second == "task_cached"
    assert len(calls) == 1
    assert calls[0]["headers"].get("Idempotency-Key") == key


@pytest.mark.asyncio
async def test_poll_render_maps_status_and_error(monkeypatch):
    _SUBMIT_IDEMPOTENCY_CACHE.clear()
    calls: list[dict[str, Any]] = []
    responses = [
        _FakeResponse(status_code=200, payload={"status": "processing"}),
        _FakeResponse(status_code=200, payload={"status": "succeeded", "video_url": "https://cdn/video.mp4"}),
        _FakeResponse(status_code=200, payload={"status": "failed", "error_message": "render failed"}),
    ]

    def fake_client_factory(*args, **kwargs):
        return _FakeAsyncClient(responses=responses, calls=calls, **kwargs)

    monkeypatch.setattr("app.services.kling_client.httpx.AsyncClient", fake_client_factory)

    client = KlingClient(api_key="kling-secret", base_url="https://kling.example")
    pending = await client.poll_render(task_id="t1")
    done = await client.poll_render(task_id="t2")
    failed = await client.poll_render(task_id="t3")

    assert pending["status"] == "rendering"
    assert done["status"] == "rendered"
    assert done["video_url"] == "https://cdn/video.mp4"
    assert failed["status"] == "failed"
    assert failed["error"] == "render failed"
