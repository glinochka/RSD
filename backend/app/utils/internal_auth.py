from secrets import compare_digest

from fastapi import Header, HTTPException, status

from ..config import settings


def verify_internal_key(x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key")) -> None:
    """
    Allow trusted service-to-service requests (bot -> backend) using a shared key.
    """
    configured_key = settings.INTERNAL_API_KEY.strip()

    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API auth is not configured",
        )

    if not x_internal_api_key or not compare_digest(x_internal_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
