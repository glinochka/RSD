import ipaddress
import hmac
import hashlib
import json
import time
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


def _build_signature_payload(*, method: str, path: str, timestamp: str, body: str) -> str:
    return "\n".join([method.upper(), path, timestamp, body])


def _compute_signature(*, payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def build_internal_request_signature(
    *,
    method: str,
    path: str,
    timestamp: str,
    body: str,
    secret: str,
) -> str:
    payload = _build_signature_payload(method=method, path=path, timestamp=timestamp, body=body)
    return _compute_signature(payload=payload, secret=secret)


async def verify_internal_signature(
    request: Request,
    x_internal_timestamp: str | None = Header(default=None, alias="X-Internal-Timestamp"),
    x_internal_signature: str | None = Header(default=None, alias="X-Internal-Signature"),
) -> None:
    secret = settings.INTERNAL_REQUEST_SIGNING_SECRET.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal request signing secret is not configured",
        )

    if not x_internal_timestamp or not x_internal_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal request signature required",
        )

    try:
        ts = int(x_internal_timestamp)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal request timestamp",
        )

    ttl = max(30, int(settings.INTERNAL_REQUEST_SIGNATURE_TTL_SECONDS))
    now = int(time.time())
    if abs(now - ts) > ttl:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal request signature expired",
        )

    raw = await request.body()
    if raw:
        try:
            body_obj = json.loads(raw.decode("utf-8"))
            canonical_body = json.dumps(body_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            canonical_body = raw.decode("utf-8", errors="ignore")
    else:
        canonical_body = ""

    expected = build_internal_request_signature(
        method=request.method,
        path=request.url.path,
        timestamp=x_internal_timestamp,
        body=canonical_body,
        secret=secret,
    )
    if not compare_digest(expected, x_internal_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal request signature",
        )
