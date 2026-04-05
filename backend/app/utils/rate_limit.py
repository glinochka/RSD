from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status


_RATE_LIMIT_STORAGE: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()


def _resolve_client_id(request: Request) -> str:
    # Trust proxy header if present; fallback to direct peer address.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    return (request.client.host if request.client else "unknown").strip() or "unknown"


def rate_limit(*, max_requests: int, window_seconds: int, scope: str):
    if max_requests <= 0 or window_seconds <= 0:
        raise ValueError("max_requests and window_seconds must be positive")

    async def dependency(request: Request) -> None:
        client_id = _resolve_client_id(request)
        storage_key = f"{scope}:{client_id}"
        now = monotonic()
        window_start = now - float(window_seconds)

        with _RATE_LIMIT_LOCK:
            bucket = _RATE_LIMIT_STORAGE[storage_key]

            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= max_requests:
                retry_after_seconds = max(1, int(bucket[0] + window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please retry later.",
                    headers={"Retry-After": str(retry_after_seconds)},
                )

            bucket.append(now)

    return dependency
