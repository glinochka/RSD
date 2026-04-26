"""YouTube OAuth + upload adapter for content_factory publishing."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_expiry(raw_value: Any) -> datetime | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1]
        return datetime.fromisoformat(value)
    except Exception:
        return None


class YouTubeClient:
    """Handles OAuth flow, token refresh and Shorts upload."""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        scopes: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._client_id = (client_id or settings.YOUTUBE_OAUTH_CLIENT_ID or "").strip()
        self._client_secret = (client_secret or settings.YOUTUBE_OAUTH_CLIENT_SECRET or "").strip()
        self._redirect_uri = (redirect_uri or settings.YOUTUBE_OAUTH_REDIRECT_URI or "").strip()
        self._scopes = (scopes or settings.YOUTUBE_OAUTH_SCOPES or "").strip()
        timeout_value = float(timeout_seconds or settings.YOUTUBE_TIMEOUT_SECONDS or 45.0)
        self._timeout = httpx.Timeout(timeout_value, connect=min(timeout_value, 10.0))
        self._max_retries = max(1, int(max_retries or settings.YOUTUBE_MAX_RETRIES or 3))
        self._oauth_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self._token_url = "https://oauth2.googleapis.com/token"
        self._api_base = "https://www.googleapis.com"

    def build_oauth_authorization_url(self, *, state: str, redirect_uri: str | None = None) -> str:
        self._assert_oauth_configured()
        effective_redirect_uri = (redirect_uri or self._redirect_uri).strip()
        if not effective_redirect_uri:
            raise RuntimeError("YouTube OAuth redirect_uri is not configured")
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": effective_redirect_uri,
                "response_type": "code",
                "scope": self._scopes,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{self._oauth_base_url}?{query}"

    async def exchange_code_for_tokens(self, *, code: str, redirect_uri: str | None = None) -> dict[str, Any]:
        self._assert_oauth_configured()
        effective_redirect_uri = (redirect_uri or self._redirect_uri).strip()
        if not effective_redirect_uri:
            raise RuntimeError("YouTube OAuth redirect_uri is required")
        payload = {
            "code": str(code or "").strip(),
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": effective_redirect_uri,
            "grant_type": "authorization_code",
        }
        if not payload["code"]:
            raise RuntimeError("OAuth code is empty")

        response = await self._request_form("POST", self._token_url, data=payload)
        access_token = str(response.get("access_token") or "").strip()
        refresh_token = str(response.get("refresh_token") or "").strip()
        if not access_token:
            raise RuntimeError("YouTube OAuth response missing access_token")
        if not refresh_token:
            raise RuntimeError("YouTube OAuth response missing refresh_token. Re-consent with prompt=consent.")
        expires_in = int(response.get("expires_in") or 3600)
        expires_at = _now_utc_naive() + timedelta(seconds=max(30, expires_in - 30))
        return {
            "provider": "youtube",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": str(response.get("token_type") or "Bearer"),
            "scope": str(response.get("scope") or self._scopes),
            "expires_at": expires_at.isoformat(),
            "redirect_uri": effective_redirect_uri,
            "connected_at": _now_utc_naive().isoformat(),
        }

    async def health_check(self, *, token_bundle: dict[str, Any]) -> dict[str, Any]:
        bundle = await self.ensure_fresh_access_token(token_bundle=token_bundle)
        profile = await self._youtube_api_get(
            path="/youtube/v3/channels",
            params={"part": "id,snippet", "mine": "true"},
            access_token=str(bundle.get("access_token") or ""),
        )
        items = profile.get("items") if isinstance(profile, dict) else None
        first = items[0] if isinstance(items, list) and items else {}
        channel_id = str(first.get("id") or "").strip()
        title = str((first.get("snippet") or {}).get("title") or "").strip()
        return {
            "ok": bool(channel_id),
            "provider": "youtube",
            "external_id": channel_id or "youtube",
            "details": {
                "title": title or None,
            },
            "token_bundle": bundle,
        }

    async def upload_short(
        self,
        *,
        token_bundle: dict[str, Any],
        video_url: str,
        title: str,
        description: str = "",
        privacy_status: str = "public",
    ) -> dict[str, Any]:
        bundle = await self.ensure_fresh_access_token(token_bundle=token_bundle)
        access_token = str(bundle.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("YouTube upload failed: empty access_token")
        src = str(video_url or "").strip()
        if not src:
            raise RuntimeError("YouTube upload failed: empty video_url")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            media_resp = await client.get(src)
            if not media_resp.is_success:
                raise RuntimeError(f"Failed to download rendered video: HTTP {media_resp.status_code}")
            media_bytes = media_resp.content
        if not media_bytes:
            raise RuntimeError("Rendered video content is empty")

        metadata = {
            "snippet": {
                "title": (title or "AI Short").strip()[:100] or "AI Short",
                "description": (description or "").strip()[:5000],
            },
            "status": {
                "privacyStatus": (privacy_status or "public").strip() or "public",
            },
        }
        resumable_url = await self._init_resumable_upload(
            access_token=access_token,
            metadata=metadata,
            content_length=len(media_bytes),
        )
        upload_result = await self._upload_resumable_bytes(
            access_token=access_token,
            resumable_url=resumable_url,
            media_bytes=media_bytes,
        )
        video_id = str(upload_result.get("id") or "").strip()
        if not video_id:
            raise RuntimeError("YouTube upload response missing video id")
        return {
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/shorts/{video_id}",
            "token_bundle": bundle,
        }

    async def ensure_fresh_access_token(self, *, token_bundle: dict[str, Any]) -> dict[str, Any]:
        bundle = dict(token_bundle or {})
        access_token = str(bundle.get("access_token") or "").strip()
        refresh_token = str(bundle.get("refresh_token") or "").strip()
        if not refresh_token:
            raise RuntimeError("YouTube token bundle missing refresh_token")
        expires_at = _parse_expiry(bundle.get("expires_at"))
        now = _now_utc_naive()
        if access_token and expires_at and expires_at > (now + timedelta(seconds=60)):
            return bundle

        response = await self._request_form(
            "POST",
            self._token_url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        new_access_token = str(response.get("access_token") or "").strip()
        if not new_access_token:
            raise RuntimeError("YouTube refresh response missing access_token")
        expires_in = int(response.get("expires_in") or 3600)
        bundle["access_token"] = new_access_token
        bundle["token_type"] = str(response.get("token_type") or bundle.get("token_type") or "Bearer")
        bundle["expires_at"] = (now + timedelta(seconds=max(30, expires_in - 30))).isoformat()
        if response.get("scope"):
            bundle["scope"] = str(response.get("scope") or "")
        return bundle

    async def _youtube_api_get(self, *, path: str, params: dict[str, Any], access_token: str) -> dict[str, Any]:
        url = f"{self._api_base}{path}"
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._request_json("GET", url, headers=headers, params=params)

    async def _init_resumable_upload(
        self,
        *,
        access_token: str,
        metadata: dict[str, Any],
        content_length: int,
    ) -> str:
        url = f"{self._api_base}/upload/youtube/v3/videos"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(content_length),
        }
        params = {"part": "snippet,status", "uploadType": "resumable"}
        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, headers=headers, params=params, json=metadata)
                if resp.is_success:
                    location = str(resp.headers.get("Location") or "").strip()
                    if not location:
                        raise RuntimeError("YouTube resumable upload response missing Location header")
                    return location
                if resp.status_code in {408, 409, 425, 429, 500, 502, 503, 504} and attempt < self._max_retries:
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                    continue
                raise RuntimeError(f"YouTube resumable init failed: HTTP {resp.status_code} {resp.text[:300]}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                    continue
                raise RuntimeError("YouTube resumable init transport failure") from exc
        raise RuntimeError(f"YouTube resumable init failed: {last_error}")

    async def _upload_resumable_bytes(
        self,
        *,
        access_token: str,
        resumable_url: str,
        media_bytes: bytes,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(media_bytes)),
        }
        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.put(resumable_url, headers=headers, content=media_bytes)
                if resp.is_success:
                    return resp.json() if resp.content else {}
                if resp.status_code in {408, 409, 425, 429, 500, 502, 503, 504} and attempt < self._max_retries:
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                    continue
                raise RuntimeError(f"YouTube upload failed: HTTP {resp.status_code} {resp.text[:300]}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                    continue
                raise RuntimeError("YouTube upload transport failure") from exc
        raise RuntimeError(f"YouTube upload failed: {last_error}")

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(method, url, headers=headers, params=params)
        if not resp.is_success:
            raise RuntimeError(f"YouTube API request failed: HTTP {resp.status_code} {resp.text[:300]}")
        if not resp.content:
            return {}
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}

    async def _request_form(self, method: str, url: str, *, data: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(method, url, data=data)
        if not resp.is_success:
            raise RuntimeError(f"YouTube OAuth request failed: HTTP {resp.status_code} {resp.text[:300]}")
        if not resp.content:
            return {}
        parsed = resp.json()
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    def _assert_oauth_configured(self) -> None:
        if not self._client_id:
            raise RuntimeError("YOUTUBE_OAUTH_CLIENT_ID is not configured")
        if not self._client_secret:
            raise RuntimeError("YOUTUBE_OAUTH_CLIENT_SECRET is not configured")


_youtube_client: YouTubeClient | None = None


def get_youtube_client() -> YouTubeClient:
    global _youtube_client
    if _youtube_client is None:
        _youtube_client = YouTubeClient()
    return _youtube_client
