"""Platform publishers for the custom content factory."""
from __future__ import annotations

import contextvars
import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from ...config import settings
from ...services.youtube_client import get_youtube_client
from .content_factory_antifraud import PHOTO_CAROUSEL_PLATFORMS, now_utc, vk_group_id

logger = logging.getLogger(__name__)

_proxy_url: contextvars.ContextVar[str] = contextvars.ContextVar("content_factory_proxy_url", default="")


class PublisherError(RuntimeError):
    pass


def open_platform_client(timeout: float) -> httpx.AsyncClient:
    """Every platform call uses the account proxy. No proxy means no socket."""
    url = str(_proxy_url.get() or "").strip()
    if not url:
        raise PublisherError("Нет прокси")
    return httpx.AsyncClient(timeout=timeout, proxy=url, trust_env=False)


def _use_proxy(proxy_url: str | None) -> contextvars.Token:
    return _proxy_url.set(str(proxy_url or "").strip())


def youtube_oauth_url(*, state: str, redirect_uri: str | None = None) -> str:
    return get_youtube_client().build_oauth_authorization_url(state=state, redirect_uri=redirect_uri)


async def youtube_exchange_code(
    *,
    code: str,
    redirect_uri: str | None = None,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    if not str(proxy_url or "").strip():
        raise PublisherError("Нет прокси")
    return await get_youtube_client().exchange_code_for_tokens(
        code=code,
        redirect_uri=redirect_uri,
        proxy=proxy_url,
    )


def publish_uses_slides(platform: str, media_kind: str) -> bool:
    return str(media_kind or "") == "carousel" and str(platform or "") in PHOTO_CAROUSEL_PLATFORMS


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
    image_urls: list[str] | None = None,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    slides = [url for url in (image_urls or []) if str(url).startswith("http")]
    if sandbox:
        kind = "карусель" if slides else "ролик"
        return {
            "status": "sandbox",
            "external_id": f"sandbox-{platform}-{video_id}-{account_id}",
            "posted_url": "",
            "note": f"Песочница: {kind} в сеть не публиковали.",
        }
    token = _use_proxy(proxy_url)
    try:
        if not str(_proxy_url.get() or "").strip():
            raise PublisherError("Нет прокси")
        prepared = await prepare_credentials(platform, credentials)
        result = await _dispatch_publish(
            platform=platform,
            credentials=prepared,
            video_url=video_url,
            title=title,
            caption=caption,
            publisher_state=publisher_state,
            slides=slides,
        )
        if prepared != dict(credentials or {}):
            result = dict(result)
            result["token_bundle"] = prepared
        return result
    finally:
        _proxy_url.reset(token)


async def _dispatch_publish(
    *,
    platform: str,
    credentials: dict[str, Any],
    video_url: str | None,
    title: str,
    caption: str,
    publisher_state: dict[str, Any] | None,
    slides: list[str],
) -> dict[str, Any]:
    if platform == "youtube":
        if slides and not str(video_url or "").strip():
            raise PublisherError("YouTube: слайд-шоу из кадров не собралось. На сервере нужен ffmpeg.")
        return await _publish_youtube(credentials=credentials, video_url=video_url, title=title, caption=caption)
    if platform == "instagram":
        if slides:
            return await _publish_instagram_carousel(
                credentials=credentials,
                image_urls=slides,
                caption=caption,
                publisher_state=publisher_state or {},
            )
        return await _publish_instagram(
            credentials=credentials,
            video_url=video_url,
            caption=caption,
            publisher_state=publisher_state or {},
        )
    if platform == "tiktok":
        if slides:
            return await _publish_tiktok_photos(
                credentials=credentials,
                image_urls=slides,
                caption=caption,
                publisher_state=publisher_state or {},
            )
        return await _publish_tiktok(
            credentials=credentials,
            video_url=video_url,
            caption=caption,
            publisher_state=publisher_state or {},
        )
    if platform == "pinterest":
        if slides:
            return await _publish_pinterest_images(credentials=credentials, image_urls=slides, title=title, caption=caption)
        return await _publish_pinterest(credentials=credentials, video_url=video_url, title=title, caption=caption)
    if platform == "vk":
        if slides and not str(video_url or "").strip():
            raise PublisherError("VK Клипы: слайд-шоу из кадров не собралось. На сервере нужен ffmpeg.")
        return await _publish_vk(
            credentials=credentials,
            video_url=video_url,
            title=title,
            caption=caption,
            publisher_state=publisher_state or {},
        )
    raise PublisherError(f"Неизвестная площадка: {platform}")


async def fetch_post_analytics(
    *,
    platform: str,
    credentials: dict[str, Any],
    external_id: str,
    proxy_url: str | None = None,
) -> dict[str, int] | None:
    if not external_id or external_id.startswith("sandbox-"):
        return None
    if not str(proxy_url or "").strip():
        return None
    token = _use_proxy(proxy_url)
    try:
        prepared = await prepare_credentials(platform, credentials)
        stats = await _fetch_stats(platform=platform, credentials=prepared, external_id=external_id)
        if isinstance(stats, dict) and prepared != dict(credentials or {}):
            stats = dict(stats)
            stats["token_bundle"] = prepared
        return stats
    except Exception as exc:
        logger.warning("Content factory analytics failed platform=%s: %s", platform, exc)
        return None
    finally:
        _proxy_url.reset(token)


async def _fetch_stats(*, platform: str, credentials: dict[str, Any], external_id: str) -> dict[str, int] | None:
    try:
        if platform == "youtube":
            return await _youtube_stats(credentials=credentials, video_id=external_id)
        if platform == "instagram":
            return await _instagram_stats(credentials=credentials, media_id=external_id)
        if platform == "tiktok":
            return await _tiktok_stats(credentials=credentials, video_id=external_id)
        if platform == "pinterest":
            return await _pinterest_stats(credentials=credentials, pin_id=external_id)
        if platform == "vk":
            return await _vk_stats(credentials=credentials, external_id=external_id)
    except Exception as exc:
        logger.warning("Content factory analytics failed platform=%s: %s", platform, exc)
    return None


async def _publish_youtube(*, credentials: dict[str, Any], video_url: str | None, title: str, caption: str) -> dict[str, Any]:
    from .content_factory_media import resolve_video_bytes

    if not str(video_url or "").strip():
        raise PublisherError("Нет готового файла для загрузки на YouTube")
    try:
        media_bytes = await resolve_video_bytes(video_url, proxy_url=str(_proxy_url.get() or ""))
    except Exception as exc:
        raise PublisherError(str(exc)) from exc
    result = await get_youtube_client().upload_short(
        token_bundle=credentials,
        video_url=str(video_url),
        title=title,
        description=caption,
        privacy_status="public",
        media_bytes=media_bytes,
        proxy=str(_proxy_url.get() or ""),
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
    async with open_platform_client(45.0) as client:
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


async def _publish_instagram_carousel(
    *,
    credentials: dict[str, Any],
    image_urls: list[str],
    caption: str,
    publisher_state: dict[str, Any],
) -> dict[str, Any]:
    """Feed carousel. Instagram Reels cannot be a photo swipe, so this is a regular carousel post."""
    token = str(credentials.get("access_token") or "").strip()
    user_id = str(credentials.get("ig_user_id") or credentials.get("external_id") or "").strip()
    if not token or not user_id:
        raise PublisherError("Instagram: нужен access_token и ig_user_id")
    container_id = str((publisher_state or {}).get("ig_container_id") or "").strip()
    async with open_platform_client(45.0) as client:
        if not container_id:
            children = []
            for url in image_urls[:10]:
                create = await client.post(
                    f"https://graph.facebook.com/v21.0/{user_id}/media",
                    data={"image_url": url, "is_carousel_item": "true", "access_token": token},
                )
                if not create.is_success:
                    raise PublisherError(f"Instagram кадр: HTTP {create.status_code} {create.text[:200]}")
                child = str((create.json() or {}).get("id") or "").strip()
                if not child:
                    raise PublisherError("Instagram не вернул кадр карусели")
                children.append(child)
            parent = await client.post(
                f"https://graph.facebook.com/v21.0/{user_id}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": ",".join(children),
                    "caption": caption[:2200],
                    "access_token": token,
                },
            )
            if not parent.is_success:
                raise PublisherError(f"Instagram карусель: HTTP {parent.status_code} {parent.text[:200]}")
            container_id = str((parent.json() or {}).get("id") or "").strip()
            if not container_id:
                raise PublisherError("Instagram не вернул карусель")
        status_resp = await client.get(
            f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": token},
        )
        code = str((status_resp.json() or {}).get("status_code") or "").upper() if status_resp.is_success else ""
        if code == "PUBLISHED":
            return {
                "status": "posted",
                "external_id": container_id,
                "posted_url": f"https://www.instagram.com/p/{container_id}/",
                "publisher_state": {"ig_container_id": container_id},
                "note": "Это карусель в ленте, не Reels: в Reels фото-листание не публикуется.",
            }
        if code != "FINISHED":
            return {
                "status": "processing",
                "external_id": container_id,
                "posted_url": "",
                "publisher_state": {"ig_container_id": container_id},
                "note": "Instagram собирает карусель. Опубликуем на следующем тике.",
            }
        publish = await client.post(
            f"https://graph.facebook.com/v21.0/{user_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
        )
        if not publish.is_success:
            return {
                "status": "processing",
                "external_id": container_id,
                "posted_url": "",
                "publisher_state": {"ig_container_id": container_id},
                "note": "Карусель ещё обрабатывается Instagram.",
            }
        media_id = str((publish.json() or {}).get("id") or container_id).strip()
    return {
        "status": "posted",
        "external_id": media_id,
        "posted_url": f"https://www.instagram.com/p/{media_id}/",
        "publisher_state": {"ig_container_id": container_id, "ig_media_id": media_id},
        "note": "Это карусель в ленте, не Reels: в Reels фото-листание не публикуется.",
    }


async def _tiktok_resume(token: str, publish_id: str) -> dict[str, Any]:
    async with open_platform_client(30.0) as client:
        response = await client.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"publish_id": publish_id},
        )
    if not response.is_success:
        raise PublisherError(f"TikTok status: HTTP {response.status_code} {response.text[:240]}")
    data = response.json() if response.content else {}
    inner = data.get("data") if isinstance(data, dict) else {}
    inner = inner if isinstance(inner, dict) else {}
    status_name = str(inner.get("status") or "").upper()
    if status_name == "FAILED":
        raise PublisherError(str(inner.get("fail_reason") or "TikTok отклонил публикацию")[:240])
    post_ids = inner.get("publicaly_available_post_id") or inner.get("publicly_available_post_id") or []
    if status_name == "PUBLISH_COMPLETE":
        public_id = str(post_ids[0]) if isinstance(post_ids, list) and post_ids else publish_id
        return {
            "status": "posted",
            "external_id": public_id,
            "posted_url": "",
            "publisher_state": {"tiktok_publish_id": publish_id},
            "note": "TikTok подтвердил публикацию.",
        }
    note = "TikTok ещё обрабатывает загрузку."
    if status_name == "SEND_TO_USER_INBOX":
        note = "TikTok положил ролик во входящие приложения: его нужно подтвердить вручную."
    return {
        "status": "processing",
        "external_id": publish_id,
        "posted_url": "",
        "publisher_state": {"tiktok_publish_id": publish_id},
        "note": note,
    }


async def _tiktok_privacy_level(token: str) -> str:
    """Prefer the privacy TikTok actually allows. A failed lookup keeps the previous public attempt."""
    try:
        async with open_platform_client(20.0) as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
    except httpx.HTTPError:
        return "PUBLIC_TO_EVERYONE"
    if not response.is_success:
        return "PUBLIC_TO_EVERYONE"
    data = response.json() if response.content else {}
    inner = data.get("data") if isinstance(data, dict) else {}
    inner = inner if isinstance(inner, dict) else {}
    options = [str(item) for item in (inner.get("privacy_level_options") or []) if item]
    if not options or "PUBLIC_TO_EVERYONE" in options:
        return "PUBLIC_TO_EVERYONE"
    raise PublisherError(
        "TikTok не разрешает публичный пост этому приложению. "
        f"Доступно: {', '.join(options)}. Нужен аудит Content Posting API."
    )


async def _publish_tiktok_photos(
    *,
    credentials: dict[str, Any],
    image_urls: list[str],
    caption: str,
    publisher_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = str(credentials.get("access_token") or "").strip()
    if not token:
        raise PublisherError("TikTok: нужен access_token")
    existing = str((publisher_state or {}).get("tiktok_publish_id") or "").strip()
    if existing:
        return await _tiktok_resume(token, existing)
    privacy = await _tiktok_privacy_level(token)
    payload = {
        "post_info": {"title": caption[:90], "privacy_level": privacy, "disable_comment": False},
        "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": image_urls[:35]},
        "post_mode": "DIRECT_POST",
        "media_type": "PHOTO",
    }
    async with open_platform_client(45.0) as client:
        response = await client.post(
            "https://open.tiktokapis.com/v2/post/publish/content/init/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    if not response.is_success:
        raise PublisherError(f"TikTok карусель: HTTP {response.status_code} {response.text[:240]}")
    data = response.json() if response.content else {}
    inner = data.get("data") if isinstance(data, dict) else {}
    publish_id = str((inner or {}).get("publish_id") or "").strip()
    if not publish_id:
        raise PublisherError("TikTok не вернул publish_id карусели")
    return {
        "status": "processing",
        "external_id": publish_id,
        "posted_url": "",
        "note": "TikTok принял фото-карусель.",
        "publisher_state": {"tiktok_publish_id": publish_id},
    }


async def _publish_pinterest_images(
    *,
    credentials: dict[str, Any],
    image_urls: list[str],
    title: str,
    caption: str,
) -> dict[str, Any]:
    token = str(credentials.get("access_token") or "").strip()
    board_id = str(credentials.get("board_id") or "").strip()
    if not token or not board_id:
        raise PublisherError("Pinterest: нужен access_token и board_id")
    if len(image_urls) >= 2:
        media = {
            "source_type": "multiple_image_urls",
            "items": [{"url": url, "title": (title or "Кадр")[:100]} for url in image_urls[:5]],
        }
    else:
        media = {"source_type": "image_url", "url": image_urls[0]}
    payload = {
        "board_id": board_id,
        "title": (title or "Карусель")[:100],
        "description": caption[:500],
        "media_source": media,
    }
    async with open_platform_client(45.0) as client:
        response = await client.post(
            "https://api.pinterest.com/v5/pins",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    if not response.is_success:
        raise PublisherError(f"Pinterest карусель: HTTP {response.status_code} {response.text[:240]}")
    data = response.json() if response.content else {}
    pin_id = str((data or {}).get("id") or "").strip()
    return {
        "status": "posted",
        "external_id": pin_id,
        "posted_url": f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else "",
    }


async def _publish_tiktok(
    *,
    credentials: dict[str, Any],
    video_url: str | None,
    caption: str,
    publisher_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = str(credentials.get("access_token") or "").strip()
    if not token:
        raise PublisherError("TikTok: нужен access_token")
    existing = str((publisher_state or {}).get("tiktok_publish_id") or "").strip()
    if existing:
        return await _tiktok_resume(token, existing)
    if not str(video_url or "").startswith("http"):
        raise PublisherError("TikTok: нет публичного URL ролика")
    privacy = await _tiktok_privacy_level(token)
    payload = {
        "post_info": {
            "title": caption[:150],
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    async with open_platform_client(45.0) as client:
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
    if not str(video_url or "").strip():
        raise PublisherError("Pinterest: нет файла ролика")
    raise PublisherError(
        "Pinterest API v5 не принимает видео по ссылке. Для этой площадки публикуйте фото-карусель. "
        "Ролики уходят на YouTube, Instagram, TikTok и VK."
    )


async def _youtube_stats(*, credentials: dict[str, Any], video_id: str) -> dict[str, int]:
    bundle = await get_youtube_client().ensure_fresh_access_token(
        token_bundle=credentials,
        proxy=str(_proxy_url.get() or ""),
    )
    access_token = str(bundle.get("access_token") or "")
    url = "https://www.googleapis.com/youtube/v3/videos?" + urlencode(
        {"part": "statistics", "id": video_id}
    )
    async with open_platform_client(20.0) as client:
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
        "token_bundle": bundle,
    }


async def _instagram_stats(*, credentials: dict[str, Any], media_id: str) -> dict[str, int]:
    token = str(credentials.get("access_token") or "").strip()
    metric_sets = (
        "plays,likes,comments,shares,saved",
        "views,likes,comments,shares,saved",
        "likes,comments,shares,saved",
    )
    last_error = "Instagram insights: пустой ответ"
    async with open_platform_client(20.0) as client:
        for metric in metric_sets:
            response = await client.get(
                f"https://graph.facebook.com/v21.0/{media_id}/insights",
                params={"metric": metric, "access_token": token},
            )
            if not response.is_success:
                last_error = f"Instagram insights HTTP {response.status_code}"
                continue
            mapped = {}
            for item in (response.json() or {}).get("data") or []:
                name = str(item.get("name") or "")
                values = item.get("values") or []
                value = int((values[0] or {}).get("value") or 0) if values else 0
                mapped[name] = value
            views_known = "plays" in mapped or "views" in mapped
            return {
                "views": int(mapped.get("plays") or mapped.get("views") or 0),
                "likes": int(mapped.get("likes") or 0),
                "comments": int(mapped.get("comments") or 0),
                "shares": int(mapped.get("shares") or 0),
                "saves": int(mapped.get("saved") or 0),
                "views_unreliable": 0 if views_known else 1,
            }
    raise PublisherError(last_error)


async def _tiktok_stats(*, credentials: dict[str, Any], video_id: str) -> dict[str, int] | None:
    token = str(credentials.get("access_token") or "").strip()
    if not token or not video_id:
        return None
    async with open_platform_client(20.0) as client:
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
    async with open_platform_client(20.0) as client:
        response = await client.get(
            f"https://api.pinterest.com/v5/pins/{pin_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if not response.is_success:
        return None
    payload = response.json() if response.content else {}
    pin_metrics = payload.get("pin_metrics") if isinstance(payload, dict) else None
    if not isinstance(pin_metrics, dict) or not pin_metrics:
        return None
    lifetime = pin_metrics.get("90d") or pin_metrics.get("lifetime") or pin_metrics
    if not isinstance(lifetime, dict) or not any(key in lifetime for key in ("impression", "save", "pin_click", "reaction")):
        return None
    views = int(lifetime.get("impression") or lifetime.get("video_avg_watch_time") or 0)
    return {
        "views": views,
        "likes": int(lifetime.get("reaction") or lifetime.get("pin_click") or 0),
        "comments": int(lifetime.get("comment") or 0),
        "shares": int(lifetime.get("outbound_click") or 0),
        "saves": int(lifetime.get("save") or 0),
    }


def vk_clip_url(owner_id: int | str, video_id: int | str) -> str:
    return f"https://vk.com/clip{int(owner_id)}_{int(video_id)}"


def _vk_error_text(payload: dict[str, Any]) -> str:
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""
    return f"{error.get('error_code')} {error.get('error_msg') or ''}".strip()


async def _vk_method(client: httpx.AsyncClient, method: str, token: str, **params: Any) -> dict[str, Any]:
    response = await client.post(
        f"https://api.vk.com/method/{method}",
        data={"access_token": token, "v": "5.199", **params},
    )
    payload = response.json() if response.content else {}
    if not isinstance(payload, dict):
        raise PublisherError(f"VK {method}: пустой ответ")
    error = _vk_error_text(payload)
    if error:
        raise PublisherError(f"VK {method}: {error}")
    result = payload.get("response")
    return result if isinstance(result, dict) else {}


async def _publish_vk(
    *,
    credentials: dict[str, Any],
    video_url: str | None,
    title: str,
    caption: str,
    publisher_state: dict[str, Any],
) -> dict[str, Any]:
    """VK Клипы: shortVideo.create → upload → shortVideo.publish."""
    from .content_factory_media import resolve_video_bytes

    token = str(credentials.get("access_token") or "").strip()
    group_id = vk_group_id(credentials.get("group_id") or credentials.get("external_id"))
    if not token or not group_id:
        raise PublisherError("VK Клипы: нужен access_token пользователя и id сообщества")
    state = publisher_state or {}
    video_id = str(state.get("vk_video_id") or "").strip()
    owner_id = str(state.get("vk_owner_id") or "").strip()
    description = (caption or title or "Клип")[:4000]
    async with open_platform_client(120.0) as client:
        if not video_id or not owner_id:
            if not str(video_url or "").strip():
                raise PublisherError("VK Клипы: нет файла слайд-шоу. На сервере нужен ffmpeg.")
            try:
                media = await resolve_video_bytes(video_url, proxy_url=str(_proxy_url.get() or ""))
            except Exception as exc:
                raise PublisherError(str(exc)) from exc
            created = await _vk_method(
                client,
                "shortVideo.create",
                token,
                group_id=group_id,
                file_size=len(media),
                description=description,
                wallpost=1,
            )
            upload_url = str(created.get("upload_url") or "").strip()
            video_id = str(created.get("video_id") or "").strip()
            owner_id = str(created.get("owner_id") or "").strip()
            if not upload_url:
                raise PublisherError("VK Клипы не вернули ссылку загрузки. Нужен пользовательский токен с правом на клипы.")
            uploaded = await client.post(
                upload_url,
                files={"file": ("clip.mp4", media, "video/mp4")},
            )
            body: dict[str, Any] = {}
            try:
                parsed = uploaded.json() if uploaded.content else {}
                if isinstance(parsed, dict):
                    body = parsed
            except Exception:
                body = {}
            video_id = str(body.get("video_id") or video_id).strip()
            owner_id = str(body.get("owner_id") or owner_id).strip()
            if not uploaded.is_success or not video_id or not owner_id:
                raise PublisherError(f"VK Клипы: загрузка файла не прошла (HTTP {uploaded.status_code})")
            return {
                "status": "processing",
                "external_id": f"{owner_id}_{video_id}",
                "posted_url": "",
                "publisher_state": {"vk_video_id": video_id, "vk_owner_id": owner_id, "vk_stage": "uploaded"},
                "note": "Клип загружен в VK. Опубликуем после обработки файла.",
            }
        try:
            await _vk_method(
                client,
                "shortVideo.edit",
                token,
                video_id=video_id,
                owner_id=owner_id,
                description=description,
            )
        except PublisherError as exc:
            logger.info("VK clip edit skipped: %s", exc)
        try:
            await _vk_method(
                client,
                "shortVideo.publish",
                token,
                video_id=video_id,
                owner_id=owner_id,
                license_agree=1,
                wallpost=1,
            )
        except PublisherError as exc:
            text = str(exc)
            if "3001" in text or "обраб" in text.lower() or "not ready" in text.lower():
                return {
                    "status": "processing",
                    "external_id": f"{owner_id}_{video_id}",
                    "posted_url": "",
                    "publisher_state": {"vk_video_id": video_id, "vk_owner_id": owner_id, "vk_stage": "uploaded"},
                    "note": "VK ещё обрабатывает клип.",
                }
            raise
    return {
        "status": "posted",
        "external_id": f"{owner_id}_{video_id}",
        "posted_url": vk_clip_url(owner_id, video_id),
        "publisher_state": {"vk_video_id": video_id, "vk_owner_id": owner_id, "vk_stage": "published"},
        "note": "Опубликован клип VK.",
    }


async def _vk_stats(*, credentials: dict[str, Any], external_id: str) -> dict[str, int] | None:
    token = str(credentials.get("access_token") or "").strip()
    raw = str(external_id or "").strip()
    if not token or "_" not in raw:
        return None
    async with open_platform_client(20.0) as client:
        payload = await _vk_method(client, "video.get", token, videos=raw)
    items = payload.get("items") if isinstance(payload, dict) else None
    first = items[0] if isinstance(items, list) and items else {}
    if not isinstance(first, dict) or not first:
        return None
    likes = first.get("likes") if isinstance(first.get("likes"), dict) else {}
    return {
        "views": int(first.get("views") or 0),
        "likes": int((likes or {}).get("count") or 0),
        "comments": int(first.get("comments") or 0),
        "shares": int(first.get("reposts", {}).get("count") or 0) if isinstance(first.get("reposts"), dict) else 0,
        "saves": 0,
    }


def _expires_at(credentials: dict[str, Any]) -> datetime | None:
    raw = str(credentials.get("expires_at") or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1]
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def _access_expired(credentials: dict[str, Any], *, within: timedelta = timedelta(seconds=60)) -> bool:
    expires = _expires_at(credentials)
    if expires is None:
        return False
    return expires <= now_utc() + within


def merge_platform_credentials(current: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    """Keep a refresh the platform already gave us when a later payload omits it."""
    merged = dict(current or {})
    for key, value in (incoming or {}).items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        merged[str(key)] = value
    refresh = str((current or {}).get("refresh_token") or "").strip()
    if refresh and not str(merged.get("refresh_token") or "").strip():
        merged["refresh_token"] = refresh
    return merged


def _app_value(*names: str) -> str:
    for name in names:
        value = str(getattr(settings, name, "") or "").strip()
        if value:
            return value
    return ""


def _app_can_rotate(platform: str) -> bool:
    if platform == "tiktok":
        return bool(_app_value("TIKTOK_CLIENT_KEY") and _app_value("TIKTOK_CLIENT_SECRET"))
    if platform == "pinterest":
        return bool(_app_value("PINTEREST_APP_ID", "PINTEREST_CLIENT_ID") and _app_value("PINTEREST_APP_SECRET", "PINTEREST_CLIENT_SECRET"))
    if platform == "vk":
        return bool(_app_value("VK_APP_ID", "VK_CLIENT_ID") and _app_value("VK_APP_SECRET", "VK_CLIENT_SECRET"))
    return False


def _token_fields(data: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    updated = dict(previous)
    access = str(data.get("access_token") or "").strip()
    if access:
        updated["access_token"] = access
    refresh = str(data.get("refresh_token") or "").strip()
    if refresh:
        updated["refresh_token"] = refresh
    expires_in = int(data.get("expires_in") or 0)
    if expires_in > 0:
        updated["expires_at"] = (now_utc() + timedelta(seconds=max(60, expires_in - 60))).isoformat()
    if data.get("token_type"):
        updated["token_type"] = str(data.get("token_type"))
    return updated


async def _rotate_instagram(credentials: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    expires = _expires_at(credentials)
    due = force or (expires is not None and expires <= now_utc() + timedelta(days=7))
    if not due:
        return credentials
    token = str(credentials.get("access_token") or "").strip()
    if not token:
        return credentials
    async with open_platform_client(20.0) as client:
        response = await client.get(
            "https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": token},
        )
    if not response.is_success:
        if _access_expired(credentials):
            raise PublisherError("Instagram: access истёк, продлить его площадка не дала.")
        return credentials
    data = response.json() if response.content else {}
    if not isinstance(data, dict) or not str(data.get("access_token") or "").strip():
        if _access_expired(credentials):
            raise PublisherError("Instagram: access истёк, продлить его площадка не дала.")
        return credentials
    updated = _token_fields(data, credentials)
    updated["token_type"] = "ig_refresh"
    return updated


async def _rotate_with_app(platform: str, credentials: dict[str, Any]) -> dict[str, Any] | None:
    if not _app_can_rotate(platform):
        return None
    refresh = str(credentials.get("refresh_token") or "").strip()
    async with open_platform_client(20.0) as client:
        if platform == "tiktok":
            response = await client.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": _app_value("TIKTOK_CLIENT_KEY"),
                    "client_secret": _app_value("TIKTOK_CLIENT_SECRET"),
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
            )
        elif platform == "pinterest":
            response = await client.post(
                "https://api.pinterest.com/v5/oauth/token",
                auth=(_app_value("PINTEREST_APP_ID", "PINTEREST_CLIENT_ID"), _app_value("PINTEREST_APP_SECRET", "PINTEREST_CLIENT_SECRET")),
                data={"grant_type": "refresh_token", "refresh_token": refresh},
            )
        elif platform == "vk":
            response = await client.post(
                "https://id.vk.com/oauth2/auth",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": _app_value("VK_APP_ID", "VK_CLIENT_ID"),
                    "device_id": str(credentials.get("device_id") or "content-factory"),
                },
            )
        else:
            return None
    if not response.is_success:
        raise PublisherError(f"{platform}: не удалось обновить access через refresh (HTTP {response.status_code})")
    data = response.json() if response.content else {}
    if not isinstance(data, dict) or not str(data.get("access_token") or "").strip():
        raise PublisherError(f"{platform}: refresh не вернул access")
    return _token_fields(data, credentials)


async def prepare_credentials(
    platform: str,
    credentials: dict[str, Any],
    *,
    force_rotate: bool = False,
) -> dict[str, Any]:
    payload = dict(credentials or {})
    name = str(platform or "").strip().lower()
    if name == "youtube":
        bundle = await get_youtube_client().ensure_fresh_access_token(
            token_bundle=payload,
            proxy=str(_proxy_url.get() or ""),
        )
        return merge_platform_credentials(payload, bundle)
    if name == "instagram":
        return await _rotate_instagram(payload, force=force_rotate)
    if _access_expired(payload):
        if str(payload.get("refresh_token") or "").strip():
            rotated = await _rotate_with_app(name, payload)
            if rotated is None:
                raise PublisherError(
                    f"{name}: access истёк. Refresh сохранён, но на сервере нет ключей приложения, обновить access нельзя."
                )
            return rotated
        raise PublisherError(f"{name}: access истёк, refresh нет. Обновить токен нечем.")
    return payload


async def _probe_identity(platform: str, credentials: dict[str, Any]) -> tuple[str | None, dict[str, str], dict[str, Any]]:
    name = str(platform or "").strip().lower()
    if name == "youtube":
        health = await get_youtube_client().health_check(
            token_bundle=credentials,
            proxy=str(_proxy_url.get() or ""),
        )
        bundle = health.get("token_bundle") if isinstance(health.get("token_bundle"), dict) else credentials
        if not health.get("ok"):
            return "YouTube не подтвердил канал через прокси аккаунта.", {}, bundle
        title = str((health.get("details") or {}).get("title") or "").strip()
        external = str(health.get("external_id") or "").strip()
        extra: dict[str, str] = {}
        if external and external != "youtube":
            extra["external_id"] = external
        if title:
            extra["display_name"] = title
        return None, extra, bundle
    async with open_platform_client(20.0) as client:
        if name == "instagram":
            user_id = str(credentials.get("ig_user_id") or credentials.get("external_id") or "").strip()
            response = await client.get(
                f"https://graph.facebook.com/v21.0/{user_id}",
                params={"fields": "id,username", "access_token": str(credentials.get("access_token") or "")},
            )
            if not response.is_success:
                return f"Instagram не подтвердил токен через прокси (HTTP {response.status_code}).", {}, credentials
            data = response.json() if response.content else {}
            username = str((data or {}).get("username") or "").strip()
            return None, ({"handle": f"@{username}"} if username else {}), credentials
        if name == "tiktok":
            response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
                headers={"Authorization": f"Bearer {credentials.get('access_token')}", "Content-Type": "application/json"},
            )
            if not response.is_success:
                return f"TikTok не подтвердил токен через прокси (HTTP {response.status_code}).", {}, credentials
            return None, {}, credentials
        if name == "pinterest":
            response = await client.get(
                "https://api.pinterest.com/v5/user_account",
                headers={"Authorization": f"Bearer {credentials.get('access_token')}"},
            )
            if not response.is_success:
                return f"Pinterest не подтвердил токен через прокси (HTTP {response.status_code}).", {}, credentials
            data = response.json() if response.content else {}
            username = str((data or {}).get("username") or "").strip()
            return None, ({"handle": username} if username else {}), credentials
        if name == "vk":
            group_id = vk_group_id(credentials.get("group_id") or credentials.get("external_id"))
            response = await client.post(
                "https://api.vk.com/method/groups.getById",
                data={
                    "access_token": str(credentials.get("access_token") or ""),
                    "v": "5.199",
                    "group_id": group_id,
                },
            )
            data = response.json() if response.content else {}
            if not isinstance(data, dict) or data.get("error"):
                return "VK не подтвердил токен сообщества через прокси.", {}, credentials
            return None, {}, credentials
    return "Площадка не подтвердила токен.", {}, credentials


async def check_platform_link(
    platform: str,
    credentials: dict[str, Any],
    *,
    proxy_url: str,
) -> tuple[dict[str, Any], str | None, dict[str, str]]:
    """Confirm the token through this account's proxy. A miss stays on the row."""
    if not str(proxy_url or "").strip():
        return dict(credentials or {}), "Нет прокси", {}
    token = _use_proxy(proxy_url)
    try:
        prepared = await prepare_credentials(platform, credentials, force_rotate=True)
        error, extra, bundle = await _probe_identity(platform, prepared)
        prepared = merge_platform_credentials(prepared, bundle)
        return prepared, error, extra
    except PublisherError as exc:
        return dict(credentials or {}), str(exc)[:500], {}
    except Exception:
        logger.info("Content factory link check failed platform=%s", platform)
        return dict(credentials or {}), "Площадка не подтвердила токен через прокси аккаунта.", {}
    finally:
        _proxy_url.reset(token)


def oauth_configured() -> bool:
    return bool((settings.YOUTUBE_OAUTH_CLIENT_ID or "").strip() and (settings.YOUTUBE_OAUTH_CLIENT_SECRET or "").strip())
