from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytest

from app.services.youtube_client import YouTubeClient


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict[str, Any] | None = None
    text: str = ""
    headers: dict[str, str] | None = None
    content_bytes: bytes | None = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def content(self) -> bytes:
        if self.content_bytes is not None:
            return self.content_bytes
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

    async def request(self, method: str, url: str, **kwargs):
        self._calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise RuntimeError("No fake responses left")
        return self._responses.pop(0)

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs):
        return await self.request("PUT", url, **kwargs)


@pytest.mark.asyncio
async def test_build_oauth_authorization_url():
    client = YouTubeClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://app.example.com/callback",
        scopes="https://www.googleapis.com/auth/youtube.upload",
    )
    url = client.build_oauth_authorization_url(state="state123")
    assert "accounts.google.com/o/oauth2/v2/auth" in url
    assert "client_id=client-id" in url
    assert "state=state123" in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens(monkeypatch):
    calls: list[dict[str, Any]] = []
    responses = [
        _FakeResponse(
            status_code=200,
            payload={
                "access_token": "ya29.new",
                "refresh_token": "refresh.new",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    ]

    def fake_client_factory(*args, **kwargs):
        return _FakeAsyncClient(responses=responses, calls=calls, **kwargs)

    monkeypatch.setattr("app.services.youtube_client.httpx.AsyncClient", fake_client_factory)

    client = YouTubeClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://app.example.com/callback",
    )
    bundle = await client.exchange_code_for_tokens(code="oauth-code")
    assert bundle["access_token"] == "ya29.new"
    assert bundle["refresh_token"] == "refresh.new"
    assert bundle["expires_at"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_upload_short_refresh_and_upload(monkeypatch):
    calls: list[dict[str, Any]] = []
    responses = [
        _FakeResponse(
            status_code=200,
            payload={"access_token": "ya29.refreshed", "expires_in": 3600, "token_type": "Bearer"},
        ),
        _FakeResponse(
            status_code=200,
            payload={"items": [{"id": "UC_ID", "snippet": {"title": "Channel"}}]},
        ),
        _FakeResponse(
            status_code=200,
            content_bytes=b"video-bytes",
        ),
        _FakeResponse(
            status_code=200,
            headers={"Location": "https://upload.session.url"},
        ),
        _FakeResponse(
            status_code=200,
            payload={"id": "VIDEO123"},
        ),
    ]

    def fake_client_factory(*args, **kwargs):
        return _FakeAsyncClient(responses=responses, calls=calls, **kwargs)

    monkeypatch.setattr("app.services.youtube_client.httpx.AsyncClient", fake_client_factory)

    client = YouTubeClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://app.example.com/callback",
    )
    stale = {
        "access_token": "expired",
        "refresh_token": "refresh.old",
        "expires_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
    }

    health = await client.health_check(token_bundle=stale)
    assert health["ok"] is True
    assert health["external_id"] == "UC_ID"

    uploaded = await client.upload_short(
        token_bundle=health["token_bundle"],
        video_url="https://cdn.example.com/video.mp4",
        title="My short",
    )
    assert uploaded["video_id"] == "VIDEO123"
    assert uploaded["video_url"] == "https://www.youtube.com/shorts/VIDEO123"
    assert len(calls) == 5
