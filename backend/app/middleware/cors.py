"""Selective CORS: strict origins for credentialed API; permissive for public widget paths."""

from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.origins import origins

# Browser calls from customer sites (widget, public booking) — API key auth, no cookies.
_PUBLIC_CORS_PREFIXES = (
    "/api/agents/external/",
    "/api/v1/agents/",
    "/public-website/",
)

_ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
_ALLOWED_HEADERS = (
    "Authorization, Content-Type, Accept, Origin, X-Requested-With, "
    "X-Internal-API-Key, X-Internal-Timestamp, X-Internal-Signature, X-Agent-API-Key"
)


def _is_public_cors_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PUBLIC_CORS_PREFIXES)


def _is_development() -> bool:
    return settings.ENVIRONMENT == "development"


def _origin_allowed_strict(origin: str) -> bool:
    if origin in origins:
        return True
    if _is_development():
        return origin.startswith("http://") or origin.startswith("https://")
    return False


class SelectiveCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get("origin")
        path = request.url.path

        if request.method == "OPTIONS" and origin:
            return self._preflight(request, origin, path)

        response = await call_next(request)
        if origin:
            self._apply_response_headers(response, origin, path)
        return response

    def _preflight(self, request: Request, origin: str, path: str) -> Response:
        headers: dict[str, str] = {
            "Access-Control-Allow-Methods": _ALLOWED_METHODS,
            "Access-Control-Allow-Headers": _ALLOWED_HEADERS,
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }

        if _is_development():
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        elif _is_public_cors_path(path):
            headers["Access-Control-Allow-Origin"] = origin
        elif _origin_allowed_strict(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        else:
            return Response(status_code=400, content="Disallowed CORS origin")

        return Response(status_code=200, content="OK", headers=headers)

    def _apply_response_headers(self, response: Response, origin: str, path: str) -> None:
        response.headers["Vary"] = "Origin"

        if _is_development():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            return

        if _is_public_cors_path(path):
            response.headers["Access-Control-Allow-Origin"] = origin
            return

        if _origin_allowed_strict(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
