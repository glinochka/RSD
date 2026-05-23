"""Guards for browser preview isolation from PSTN media stack (stage 9)."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

BROWSER_PREVIEW_CHANNEL = "browser_preview"
BROWSER_PREVIEW_SOURCE = "browser_preview"

# Substrings that must never appear in preview outbound HTTP targets.
_FORBIDDEN_MEDIA_GATEWAY_MARKERS = (
    "telephony_media_gateway",
    ":8200/ws",
    "/ws/media",
    "TELEPHONY_MEDIA_WS_URL",
)


def assert_preview_channel(channel: str | None) -> None:
    normalized = (channel or "").strip().lower()
    if normalized and normalized != BROWSER_PREVIEW_CHANNEL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Preview supports only channel={BROWSER_PREVIEW_CHANNEL}",
        )


def assert_no_media_gateway_url(url: str | None) -> None:
    """Reject accidental preview → media gateway wiring."""
    raw = (url or "").strip().lower()
    if not raw:
        return
    for marker in _FORBIDDEN_MEDIA_GATEWAY_MARKERS:
        if marker.lower() in raw:
            logger.error("preview blocked media gateway url marker=%s", marker)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Browser preview cannot use telephony media gateway",
            )


def assert_preview_isolated() -> None:
    """Runtime guard: preview path must not depend on media gateway env."""
    from ..config import settings

    media_ws = (getattr(settings, "TELEPHONY_MEDIA_WS_URL", None) or "").strip()
    assert_no_media_gateway_url(media_ws)
