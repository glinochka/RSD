"""Platform publishers for the custom content factory."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from ...config import settings
from ...services.youtube_client import get_youtube_client

logger = logging.getLogger(__name__)


class PublisherError(RuntimeError):
    pass


def youtube_oauth_url(*, state: str, redirect_uri: str | None = None) -> str:
    return get_youtube_client().build_oauth_authorization_url(state=state, redirect_uri=redirect_uri)


async def youtube_exchange_code(*, code: str, redirect_uri: str | None = None) -> dict[str, Any]:
    return await get_youtube_client().exchange_code_for_tokens(code=code, redirect_uri=redirect_uri)


async def publish_to_platform(
    *,
    platform: str,
    credentials: dict[str, Any],
    video_url: str | None,
    title: str,
    caption: str,
    sandbox: bool,
    video_id: int,
    account_id: int,
    publisher_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if sandbox:
        return {
            "status": "sandbox",
            "external_id": f"sandbox-{platform}-{video_id}-{account_id}",
            "posted_url": "",
            "note": "Песочница: в сеть не публиковали.",
        }
    if platform == "youtube":
        return await _publish_youtube(credentials=credentials, video_url=video_url, title=title, caption=caption)
    if platform == "instagram":
        return await _publish_instagram(
            credentials=credentials,
            video_url=video_url,
            caption=caption,
            publisher_state=publisher_state or {},
        )
    if platform == "tiktok":
        return await _publish_tiktok(credentials=credentials, video_url=video_url, caption=caption)
    if platform == "pinterest":
        return await _publish_pinterest(credentials=credentials, video_url=video_url, title=title, caption=caption)
    raise PublisherError(f"Неизвестная площадка: {platform}")


async def fetch_post_analytics(*, platform: str, credentials: dict[str, Any], external_id: str) -> dict[str, int] | None:
    if not external_id or external_id.startswith("sandbox-"):
        return None
    try:
        if platform == "youtube":
            return await _youtube_stats(credentials=credentials, video_id=external_id)
        if platform == "instagram":
            return await _instagram_stats(credentials=credentials, media_id=external_id)
        if platform == "tiktok":
            return await _tiktok_stats(credentials=credentials, video_id=external_id)
        if platform == "pinterest":
            return await _pinterest_stats(credentials=credentials, pin_id=external_id)
    except Exception as exc:
        logger.warning("Content factory analytics failed platform=%s: %s", platform, exc)
    return None


async def _publish_youtube(*, credentials: dict[str, Any], video_url: str | None, title: str, caption: str) -> dict[str, Any]:
    from .content_factory_media import resolve_video_bytes

    if not str(video_url or "").strip():
        raise PublisherError("Нет готового файла для загрузки на YouTube")
    try:
        media_bytes = await resolve_video_bytes(video_url)
    except Exception as exc:
        raise PublisherError(str(exc)) from exc
    result = await get_youtube_client().upload_short(
        token_bundle=credentials,
        video_url=str(video_url),
        title=title,
        description=caption,
        privacy_status="public",
        media_bytes=media_bytes,
    )
    return {
        "status": "posted",
        "external_id": str(result.get("video_id") or ""),
        "posted_url": str(result.get("video_url") or ""),
        "token_bundle": result.get("token_bundle") or credentials,
    }


async def _publish_instagram(
    *,
    credentials: dict[str, Any],
    video_url: str | None,
    caption: str,
    publisher_state: dict[str, Any],
) -> dict[str, Any]:
    token = str(credentials.get("access_token") or "").strip()
    user_id = str(credentials.get("ig_user_id") or credentials.get("external_id") or "").strip()
    if not token or not user_id:
        raise PublisherError("Instagram: нужен access_token и ig_user_id")
    if not str(video_url or "").startswith("http"):
        raise PublisherError("Instagram: нет публичного URL ролика")
    container_id = str((publisher_state or {}).get("ig_container_id") or "").strip()
    async with httpx.AsyncClient(timeout=45.0) as client:
        if not container_id:
            create = await client.post(
                f"https://graph.facebook.com/v21.0/{user_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption[:2200],
                    "share_to_feed": "true",
                    "access_token": token,
                },
            )
            if not create.is_success:
                raise PublisherError(f"Instagram container: HTTP {create.status_code} {create.text[:240]}")
            container_id = str((create.json() or {}).get("id") or "").strip()
            if not container_id:
                raise PublisherError("Instagram не вернул id контейнера")
            return {
                "status": "processing",
                "external_id": container_id,
                "posted_url": "",
                "publisher_state": {"ig_container_id": container_id},
                "note": "Instagram обрабатывает контейнер Reels. Опубликуем на следующем тике.",
            }
        status_resp = await client.get(
            f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": token},
        )
        if not status_resp.is_success:
            raise PublisherError(f"Instagram status: HTTP {status_resp.status_code} {status_resp.text[:240]}")
        code = str((status_resp.json() or {}).get("status_code") or "").upper()
        if code == "ERROR":
            raise PublisherError("Instagram отклонил контейнер Reels")
        if code == "PUBLISHED":
            return {
                "status": "posted",
                "external_id": container_id,
                "posted_url": f"https://www.instagram.com/reel/{container_id}/",
                "publisher_state": {"ig_container_id": container_id},
            }
        if code != "FINISHED":
            return {
                "status": "processing",
                "external_id": container_id,
                "posted_url": "",
                "publisher_state": {"ig_container_id": container_id},
                "note": "Instagram ещё обрабатывает Reels.",
            }
        publish = await client.post(
            f"https://graph.facebook.com/v21.0/{user_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
        )
        if not publish.is_success:
            raise PublisherError(f"Instagram publish: HTTP {publish.status_code} {publish.text[:240]}")
        media_id = str((publish.json() or {}).get("id") or container_id).strip()
    return {
        "status": "posted",
        "external_id": media_id,
        "posted_url": f"https://www.instagram.com/reel/{media_id}/",
        "publisher_state": {"ig_container_id": container_id, "ig_media_id": media_id},
    }


async def _publish_tiktok(*, credentials: dict[str, Any], video_url: str | None, caption: str) -> dict[str, Any]:
    token = str(credentials.get("access_token") or "").strip()
    if not token:
        raise PublisherError("TikTok: нужен access_token")
    if not str(video_url or "").startswith("http"):
        raise PublisherError("TikTok: нет публичного URL ролика")
    payload = {
        "post_info": {
            "title": caption[:150],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    if not response.is_success:
        raise PublisherError(f"TikTok publish: HTTP {response.status_code} {response.text[:240]}")
    data = response.json() if response.content else {}
    inner = data.get("data") if isinstance(data, dict) else {}
    publish_id = str((inner or {}).get("publish_id") or (inner or {}).get("id") or "").strip()
    share_url = str((inner or {}).get("share_url") or "").strip()
    if not publish_id and not share_url:
        raise PublisherError("TikTok не вернул publish_id")
    if share_url:
        return {
            "status": "posted",
            "external_id": publish_id,
            "posted_url": share_url,
        }
    return {
        "status": "processing",
        "external_id": publish_id,
        "posted_url": "",
        "note": "TikTok принял ролик. Если публикация не появится, подтвердите её в приложении (inbox Content Posting API).",
        "publisher_state": {"tiktok_publish_id": publish_id},
    }


async def _publish_pinterest(*, credentials: dict[str, Any], video_url: str | None, title: str, caption: str) -> dict[str, Any]:
    token = str(credentials.get("access_token") or "").strip()
    board_id = str(credentials.get("board_id") or "").strip()
    if not token or not board_id:
        raise PublisherError("Pinterest: нужен access_token и board_id")
    if not str(video_url or "").startswith("http"):
        raise PublisherError("Pinterest: нет публичного URL ролика")
    payload = {
        "board_id": board_id,
        "title": (title or "Idea pin")[:100],
        "description": caption[:500],
        "media_source": {"source_type": "video_url", "url": video_url},
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://api.pinterest.com/v5/pins",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    if not response.is_success:
        raise PublisherError(f"Pinterest pin: HTTP {response.status_code} {response.text[:240]}")
    data = response.json() if response.content else {}
    pin_id = str((data or {}).get("id") or "").strip()
    link = str((data or {}).get("link") or "")
    return {
        "status": "posted",
        "external_id": pin_id,
        "posted_url": link or (f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else ""),
    }


async def _youtube_stats(*, credentials: dict[str, Any], video_id: str) -> dict[str, int]:
    bundle = await get_youtube_client().ensure_fresh_access_token(token_bundle=credentials)
    access_token = str(bundle.get("access_token") or "")
    url = "https://www.googleapis.com/youtube/v3/videos?" + urlencode(
        {"part": "statistics", "id": video_id}
    )
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
    if not response.is_success:
        raise PublisherError(f"YouTube stats HTTP {response.status_code}")
    items = (response.json() or {}).get("items") or []
    stats = (items[0].get("statistics") if items else {}) or {}
    return {
        "views": int(stats.get("viewCount") or 0),
        "likes": int(stats.get("likeCount") or 0),
        "comments": int(stats.get("commentCount") or 0),
        "shares": 0,
        "saves": 0,
    }


async def _instagram_stats(*, credentials: dict[str, Any], media_id: str) -> dict[str, int]:
    token = str(credentials.get("access_token") or "").strip()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://graph.facebook.com/v21.0/{media_id}/insights",
            params={"metric": "plays,likes,comments,shares,saved", "access_token": token},
        )
    if not response.is_success:
        raise PublisherError(f"Instagram insights HTTP {response.status_code}")
    mapped = {}
    for item in (response.json() or {}).get("data") or []:
        name = str(item.get("name") or "")
        values = item.get("values") or []
        value = int((values[0] or {}).get("value") or 0) if values else 0
        mapped[name] = value
    return {
        "views": mapped.get("plays") or 0,
        "likes": mapped.get("likes") or 0,
        "comments": mapped.get("comments") or 0,
        "shares": mapped.get("shares") or 0,
        "saves": mapped.get("saved") or 0,
    }


async def _tiktok_stats(*, credentials: dict[str, Any], video_id: str) -> dict[str, int] | None:
    token = str(credentials.get("access_token") or "").strip()
    if not token or not video_id:
        return None
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://open.tiktokapis.com/v2/video/query/",
            params={"fields": "id,like_count,comment_count,share_count,view_count"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"filters": {"video_ids": [video_id]}},
        )
    if not response.is_success:
        return None
    items = ((response.json() or {}).get("data") or {}).get("videos") or []
    first = items[0] if items else {}
    if not first:
        return None
    return {
        "views": int(first.get("view_count") or 0),
        "likes": int(first.get("like_count") or 0),
        "comments": int(first.get("comment_count") or 0),
        "shares": int(first.get("share_count") or 0),
        "saves": 0,
    }


async def _pinterest_stats(*, credentials: dict[str, Any], pin_id: str) -> dict[str, int] | None:
    token = str(credentials.get("access_token") or "").strip()
    if not token or not pin_id:
        return None
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.pinterest.com/v5/pins/{pin_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if not response.is_success:
        return None
    payload = response.json() if response.content else {}
    pin_metrics = (payload.get("pin_metrics") or {}) if isinstance(payload, dict) else {}
    lifetime = pin_metrics.get("90d") or pin_metrics.get("lifetime") or pin_metrics
    if not isinstance(lifetime, dict):
        return None
    views = int(lifetime.get("impression") or lifetime.get("video_avg_watch_time") or 0)
    return {
        "views": views,
        "likes": int(lifetime.get("reaction") or lifetime.get("pin_click") or 0),
        "comments": int(lifetime.get("comment") or 0),
        "shares": int(lifetime.get("outbound_click") or 0),
        "saves": int(lifetime.get("save") or 0),
    }


def oauth_configured() -> bool:
    return bool((settings.YOUTUBE_OAUTH_CLIENT_ID or "").strip() and (settings.YOUTUBE_OAUTH_CLIENT_SECRET or "").strip())
