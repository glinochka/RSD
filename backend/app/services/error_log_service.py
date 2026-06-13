"""Persist application errors for admin bug tracking."""

from __future__ import annotations

import json
import traceback
from logging import getLogger
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Request

from ..alembic.database import async_session_maker
from ..config import get_auth_data
from ..router_admin.dao import ApplicationErrorLogDAO
from ..utils.pii import redact_pii_text

logger = getLogger(__name__)

_MAX_MESSAGE_LEN = 8000
_MAX_TRACEBACK_LEN = 32000
_MAX_SCENARIO_LEN = 512
_SKIP_PATH_PREFIXES = ("/api/admin/logs",)


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _format_http_exception_detail(detail: Any) -> str:
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(detail)


def _extract_user_id_from_request(request: Request | None) -> int | None:
    if request is None:
        return None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None

    for token_kind in ("user", "admin", "sales_staff"):
        try:
            auth_data = get_auth_data(token_kind)
            secret_key = auth_data["secret_key"]
            algorithm = auth_data["algorithm"]
            if isinstance(secret_key, str):
                secret_key = secret_key.encode("utf-8")
            data = jwt.decode(token, secret_key, algorithms=[algorithm])
            if data.get("token_kind") != token_kind:
                continue
            user_id = data.get("user_id")
            if user_id is not None:
                return int(user_id)
        except (InvalidTokenError, ValueError, TypeError):
            continue
    return None


def build_request_context(request: Request | None) -> dict[str, Any] | None:
    if request is None:
        return None

    query_params = dict(request.query_params.multi_items())
    context: dict[str, Any] = {
        "method": request.method,
        "path": request.url.path,
        "query": query_params or None,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    referer = request.headers.get("referer")
    if referer:
        context["referer"] = referer

    redacted = redact_pii_text(json.dumps(context, ensure_ascii=False, default=str))
    try:
        return json.loads(redacted)
    except json.JSONDecodeError:
        return {"raw": redacted}


def build_api_scenario(request: Request | None) -> str:
    if request is None:
        return "unknown request"
    return f"{request.method} {request.url.path}"


def should_skip_request_logging(request: Request | None) -> bool:
    if request is None:
        return False
    path = request.url.path
    return any(path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES)


async def record_error_log(
    *,
    exc: BaseException,
    source: str = "api",
    scenario: str | None = None,
    level: str = "error",
    status_code: int | None = None,
    request: Request | None = None,
    context: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> None:
    if request is not None and should_skip_request_logging(request):
        return

    try:
        error_type = type(exc).__name__
        message = _format_http_exception_detail(getattr(exc, "detail", None)) or str(exc) or error_type
        message = redact_pii_text(_truncate(message, _MAX_MESSAGE_LEN) or error_type)

        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        tb = redact_pii_text(_truncate(tb, _MAX_TRACEBACK_LEN))

        resolved_scenario = _truncate(
            scenario or build_api_scenario(request),
            _MAX_SCENARIO_LEN,
        ) or "unknown"

        request_context = build_request_context(request)
        if context:
            merged = {**(request_context or {}), **context}
            request_context = merged

        resolved_user_id = user_id if user_id is not None else _extract_user_id_from_request(request)

        async with async_session_maker() as session:
            log_dao = ApplicationErrorLogDAO(session)
            async with session.begin():
                await log_dao.add(
                    {
                        "level": level,
                        "source": source[:64],
                        "scenario": resolved_scenario,
                        "error_type": error_type[:255],
                        "message": message,
                        "traceback": tb,
                        "context_json": request_context,
                        "user_id": resolved_user_id,
                        "status_code": status_code,
                    }
                )
    except Exception:
        logger.exception("Failed to persist application error log")
