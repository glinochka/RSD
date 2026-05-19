"""Internal API auth for telephony bridge → backend."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import Header, HTTPException, Request, status

from ..config import settings
from ..utils.internal_auth import is_request_secure


def _configured_telephony_internal_key() -> str:
    key = settings.TELEPHONY_INTERNAL_API_KEY.strip() or settings.INTERNAL_API_KEY.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telephony internal API auth is not configured",
        )
    return key


def is_telephony_internal_request(
    request: Request,
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> bool:
    try:
        configured_key = _configured_telephony_internal_key()
    except HTTPException:
        return False
    if not x_internal_api_key or not compare_digest(x_internal_api_key, configured_key):
        return False
    if not is_request_secure(request) and not settings.ALLOW_INSECURE_INTERNAL_API:
        return False
    return True


async def require_telephony_internal(request: Request, internal: bool) -> None:
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    if not is_request_secure(request) and not settings.ALLOW_INSECURE_INTERNAL_API:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telephony internal API requires private network or TLS",
        )
    from ..utils.internal_auth import verify_internal_signature

    await verify_internal_signature(request)
