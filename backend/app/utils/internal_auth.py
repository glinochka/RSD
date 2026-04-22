import ipaddress
from secrets import compare_digest

from fastapi import Header, HTTPException, Request, status

from ..config import settings


def _get_configured_internal_key() -> str:
    configured_key = settings.INTERNAL_API_KEY.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API auth is not configured",
        )
    return configured_key


def is_request_secure(request: Request) -> bool:
    # Prefer reverse-proxy signal when available.
    forwarded_proto = request.headers.get("x-forwarded-proto", "").strip().lower()
    if forwarded_proto == "https":
        return True

    if request.url.scheme == "https":
        return True

    # Allow local/private-network traffic to support isolated internal services.
    host = (request.client.host if request.client else "").strip()
    if not host:
        return False
    if host in {"127.0.0.1", "::1", "localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Non-IP hostname should require TLS unless explicitly allowed.
        return settings.ALLOW_INSECURE_INTERNAL_API
    return ip.is_private or ip.is_loopback or ip.is_link_local


def verify_internal_key(
    request: Request,
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> None:
    """
    Allow trusted service-to-service requests (bot -> backend) using a shared key.
    """
    configured_key = _get_configured_internal_key()

    if not x_internal_api_key or not compare_digest(x_internal_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
    if not is_request_secure(request) and not settings.ALLOW_INSECURE_INTERNAL_API:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal API requires a secure transport",
        )


def is_internal_request(
    request: Request,
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> bool:
    try:
        configured_key = _get_configured_internal_key()
    except HTTPException:
        return False
    if not x_internal_api_key or not compare_digest(x_internal_api_key, configured_key):
        return False
    if not is_request_secure(request) and not settings.ALLOW_INSECURE_INTERNAL_API:
        return False
    return True
