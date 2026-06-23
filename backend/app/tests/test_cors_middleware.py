"""Tests for selective CORS middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.cors import SelectiveCORSMiddleware


def _make_request(method: str, path: str, origin: str | None = "https://evil.example") -> Request:
    headers = []
    if origin:
        headers.append((b"origin", origin.encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_production_blocks_evil_origin_on_users_me(monkeypatch):
    monkeypatch.setattr("app.middleware.cors.settings.ENVIRONMENT", "production")

    middleware = SelectiveCORSMiddleware(app=MagicMock())
    request = _make_request("OPTIONS", "/api/users/me")

    response = await middleware.dispatch(request, AsyncMock())

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_production_allows_widget_path_without_credentials(monkeypatch):
    monkeypatch.setattr("app.middleware.cors.settings.ENVIRONMENT", "production")

    async def call_next(_request):
        return Response(content="ok")

    middleware = SelectiveCORSMiddleware(app=MagicMock())
    request = _make_request("GET", "/api/agents/external/chat")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://evil.example"
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.asyncio
async def test_production_allows_configured_origin_with_credentials(monkeypatch):
    monkeypatch.setattr("app.middleware.cors.settings.ENVIRONMENT", "production")
    monkeypatch.setattr(
        "app.middleware.cors.origins",
        ["https://rsd-ai.ru"],
    )

    async def call_next(_request):
        return Response(content="ok")

    middleware = SelectiveCORSMiddleware(app=MagicMock())
    request = _make_request("GET", "/api/users/me", origin="https://rsd-ai.ru")

    response = await middleware.dispatch(request, call_next)

    assert response.headers.get("access-control-allow-origin") == "https://rsd-ai.ru"
    assert response.headers.get("access-control-allow-credentials") == "true"
