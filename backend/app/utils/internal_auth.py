from fastapi import Header, HTTPException, status

from ..config import settings


def verify_internal_key(x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key")) -> None:
    """
    Allow trusted service-to-service requests (bot -> backend) using a shared key.
    """
    configured_key = settings.INTERNAL_API_KEY.strip()

    # Development/upgrade safety:
    # if INTERNAL_API_KEY is not configured, do not block internal traffic entirely.
    # We still require the header to be present (bot sends it), otherwise reject.
    if not configured_key:
        if x_internal_api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="INTERNAL_API_KEY is not configured (missing header)",
            )
        return

    if x_internal_api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
