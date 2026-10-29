"""CRUD and snapshots for the custom AI content factory."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...alembic.models import (
    CustomContentFactoryAccount,
    CustomContentFactoryPost,
    CustomContentFactorySettings,
    CustomContentFactoryTokenUsage,
    CustomContentFactoryVideo,
    CustomContentFactoryWarmupEvent,
)
from ...utils.crypto import decrypt_token, encrypt_token
from ...config import settings as app_settings
from .content_factory_antifraud import (
    CONTENT_FORMATS,
    PLATFORMS,
    VIDEO_IN_FLIGHT,
    VISUAL_STYLES,
    compute_health_score,
    in_posting_window,
    next_enqueue_at,
    now_utc,
    uniqualize_recipe,
    validate_platform_credentials,
    warmup_progress,
)

SECRET_FIELDS = (
    "openai_api_key",
    "anthropic_api_key",
    "kling_api_key",
    "runway_api_key",
    "luma_api_key",
    "elevenlabs_api_key",
    "xai_api_key",
)

DEFAULT_FORMATS = ["educational", "storytelling"]
DEFAULT_STYLES = ["realism", "motion"]


def _as_list(value: Any, allowed: tuple[str, ...] | None = None) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value if str(part).strip()]
    else:
        items = []
    if allowed:
        items = [item for item in items if item in allowed]
    return items


def _secret_set(value: str | None) -> bool:
    return bool(str(value or "").strip())


def encrypt_json(payload: dict[str, Any]) -> str:
    return encrypt_token(json.dumps(payload, ensure_ascii=False))


def decrypt_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(decrypt_token(raw))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def get_or_create_settings(session: AsyncSession, automation_id: int) -> CustomContentFactorySettings:
    row = await session.scalar(
        select(CustomContentFactorySettings).where(
            CustomContentFactorySettings.custom_automation_id == automation_id
        )
    )
    if row:
        if not row.content_formats:
            row.content_formats = list(DEFAULT_FORMATS)
        if not row.visual_styles:
            row.visual_styles = list(DEFAULT_STYLES)
        return row
    row = CustomContentFactorySettings(
        custom_automation_id=automation_id,
        content_formats=list(DEFAULT_FORMATS),
        visual_styles=list(DEFAULT_STYLES),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(row)
    await session.flush()
    return row


def serialize_settings(row: CustomContentFactorySettings) -> dict[str, Any]:
    return {
        "id": row.id,
        "enabled": bool(row.enabled),
        "sandbox_mode": bool(row.sandbox_mode),
        "product_name": row.product_name,
        "product_description": row.product_description,
        "product_url": row.product_url,
        "cta_text": row.cta_text,
        "audience": row.audience,
        "niche": row.niche,
        "content_formats": list(row.content_formats or []),
        "visual_styles": list(row.visual_styles or []),
        "language": row.language,
        "tone": row.tone,
        "brand_voice": row.brand_voice,
        "forbidden_topics": row.forbidden_topics,
        "videos_per_day": float(row.videos_per_day or 1),
        "duration_min": int(row.duration_min or 30),
        "duration_max": int(row.duration_max or 45),
        "aspect_ratio": row.aspect_ratio,
        "posting_window_start": row.posting_window_start,
        "posting_window_end": row.posting_window_end,
        "timezone": row.timezone,
        "idea_model": row.idea_model,
        "script_model": row.script_model,
        "video_model": row.video_model,
        "tts_model": row.tts_model or "",
        "carousel_share": int(getattr(row, "carousel_share", 100) if getattr(row, "carousel_share", None) is not None else 100),
        "music_mode": getattr(row, "music_mode", None) or "voice_bed",
        "music_volume": int(getattr(row, "music_volume", 32) or 32),
        "tts_voice": getattr(row, "tts_voice", None) or "",
        "image_provider": getattr(row, "image_provider", None) or "chatgpt",
        "image_model": getattr(row, "image_model", None) or "gpt-image-2.5-flare",
        "openai_api_key_set": _secret_set(row.openai_api_key_enc),
        "anthropic_api_key_set": _secret_set(row.anthropic_api_key_enc),
        "kling_api_key_set": _secret_set(row.kling_api_key_enc),
        "runway_api_key_set": _secret_set(row.runway_api_key_enc),
        "luma_api_key_set": _secret_set(row.luma_api_key_enc),
        "elevenlabs_api_key_set": _secret_set(row.elevenlabs_api_key_enc),
        "xai_api_key_set": _secret_set(getattr(row, "xai_api_key_enc", None)),
        "grok_bot_id": f"cf-carousel-{row.custom_automation_id}",
        "grok_bot_name": getattr(row, "grok_bot_name", None) or "Карусели завода",
        "grok_bot_brief": getattr(row, "grok_bot_brief", None) or "",
        "grok_bot_has_thread": bool(str(getattr(row, "grok_bot_response_id", "") or "").strip()),
        "warmup_days": int(row.warmup_days or 7),
        "warmup_actions_per_day": int(row.warmup_actions_per_day or 8),
        "max_posts_per_account_per_day": int(row.max_posts_per_account_per_day or 2),
        "stagger_min_minutes": int(row.stagger_min_minutes or 25),
        "uniqualize_enabled": bool(row.uniqualize_enabled),
        "unique_per_platform": bool(row.unique_per_platform),
        "hook_required": bool(row.hook_required),
        "avoid_exact_hour": bool(row.avoid_exact_hour),
        "shadowban_pause_zero_views": bool(row.shadowban_pause_zero_views),
        "shadowban_zero_views_threshold": int(row.shadowban_zero_views_threshold or 3),
        "last_enqueued_at": _dt(row.last_enqueued_at),
        "updated_at": _dt(row.updated_at),
    }


def apply_settings_update(row: CustomContentFactorySettings, payload: dict[str, Any]) -> CustomContentFactorySettings:
    mapping = {
        "enabled": lambda v: bool(v),
        "sandbox_mode": lambda v: bool(v),
        "product_name": lambda v: str(v or "")[:200],
        "product_description": lambda v: str(v or "")[:8000],
        "product_url": lambda v: str(v or "")[:512],
        "cta_text": lambda v: str(v or "")[:200],
        "audience": lambda v: str(v or "")[:4000],
        "niche": lambda v: str(v or "")[:128],
        "language": lambda v: str(v or "ru")[:16],
        "tone": lambda v: str(v or "expert_friendly")[:64],
        "brand_voice": lambda v: str(v or "")[:4000],
        "forbidden_topics": lambda v: str(v or "")[:2000],
        "videos_per_day": lambda v: max(0.2, min(float(v or 1), 8.0)),
        "duration_min": lambda v: max(8, min(int(v or 30), 90)),
        "duration_max": lambda v: max(8, min(int(v or 45), 120)),
        "aspect_ratio": lambda v: v if v in {"9:16", "16:9", "1:1"} else "9:16",
        "posting_window_start": lambda v: str(v or "09:00")[:8],
        "posting_window_end": lambda v: str(v or "21:00")[:8],
        "timezone": lambda v: str(v or "Europe/Moscow")[:64],
        "idea_model": lambda v: str(v or "deepseek-chat")[:128],
        "script_model": lambda v: str(v or "deepseek-chat")[:128],
        "video_model": lambda v: str(v or "kling")[:128],
        "tts_model": lambda v: str(v or "")[:128],
        "carousel_share": lambda v: max(0, min(int(v or 0), 100)),
        "music_mode": lambda v: v if v in {"off", "bed", "voice", "voice_bed"} else "voice_bed",
        "music_volume": lambda v: max(0, min(int(v or 32), 100)),
        "tts_voice": lambda v: str(v or "")[:64],
        "image_provider": lambda v: v if v in {"chatgpt", "grok"} else "chatgpt",
        "image_model": lambda v: str(v or "gpt-image-2.5-flare")[:128],
        "grok_bot_name": lambda v: str(v or "Карусели завода")[:80],
        "grok_bot_brief": lambda v: str(v or "")[:4000],
        "warmup_days": lambda v: max(1, min(int(v or 7), 30)),
        "warmup_actions_per_day": lambda v: max(2, min(int(v or 8), 20)),
        "max_posts_per_account_per_day": lambda v: max(1, min(int(v or 2), 8)),
        "stagger_min_minutes": lambda v: max(5, min(int(v or 25), 240)),
        "uniqualize_enabled": lambda v: bool(v),
        "unique_per_platform": lambda v: bool(v),
        "hook_required": lambda v: bool(v),
        "avoid_exact_hour": lambda v: bool(v),
        "shadowban_pause_zero_views": lambda v: bool(v),
        "shadowban_zero_views_threshold": lambda v: max(2, min(int(v or 3), 10)),
    }
    for key, caster in mapping.items():
        if key in payload and payload[key] is not None:
            setattr(row, key, caster(payload[key]))
    if row.duration_max < row.duration_min:
        row.duration_max = row.duration_min
    if "content_formats" in payload and payload["content_formats"] is not None:
        formats = _as_list(payload["content_formats"], CONTENT_FORMATS)
        row.content_formats = formats or list(DEFAULT_FORMATS)
    if "visual_styles" in payload and payload["visual_styles"] is not None:
        styles = _as_list(payload["visual_styles"], VISUAL_STYLES)
        row.visual_styles = styles or list(DEFAULT_STYLES)
    for field in SECRET_FIELDS:
        raw = payload.get(field)
        if isinstance(raw, str) and raw.strip():
            setattr(row, f"{field}_enc", encrypt_token(raw.strip()))
        if payload.get(f"clear_{field}"):
            setattr(row, f"{field}_enc", None)
    row.updated_at = now_utc()
    return row


def sync_module_flag(automation, enabled: bool) -> None:
    blob = dict(getattr(automation, "module_settings", None) or {})
    current = dict(blob.get("content_factory") or {})
    current["enabled"] = bool(enabled)
    blob["content_factory"] = current
    automation.module_settings = blob


def decrypted_secret(row: CustomContentFactorySettings, field: str) -> str:
    raw = getattr(row, f"{field}_enc", None)
    if not raw:
        return ""
    try:
        return decrypt_token(raw)
    except Exception:
        return ""


def serialize_warmup_event(row: CustomContentFactoryWarmupEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "action_type": row.action_type,
        "result": row.result,
        "detail": row.detail,
        "created_at": _dt(row.created_at),
    }


def serialize_account(
    row: CustomContentFactoryAccount,
    settings: CustomContentFactorySettings,
    *,
    warmup_events: list[CustomContentFactoryWarmupEvent] | None = None,
) -> dict[str, Any]:
    progress = warmup_progress(
        started_at=row.warmup_started_at,
        completed_at=row.warmup_completed_at,
        actions_done=int(row.warmup_actions_done or 0),
        warmup_days=int(settings.warmup_days or 7),
        actions_per_day=int(settings.warmup_actions_per_day or 8),
    )
    creds = decrypt_json(row.credentials_enc)
    events = list(warmup_events or [])[:5]
    score = compute_health_score(
        status=row.status,
        warmup_complete=bool(progress.get("complete")),
        last_error=row.last_error,
        risk_flags=list(row.risk_flags or []),
        recent_views=0,
    )
    return {
        "id": row.id,
        "platform": row.platform,
        "display_name": row.display_name,
        "handle": row.handle,
        "external_id": row.external_id,
        "status": row.status,
        "is_enabled": bool(row.is_enabled),
        "has_credentials": bool(creds),
        "warmup": progress,
        "warmup_events": [serialize_warmup_event(item) for item in events[:5]],
        "last_posted_at": _dt(row.last_posted_at),
        "posts_today": int(row.posts_today or 0),
        "health_score": score,
        "risk_flags": list(row.risk_flags or []),
        "last_error": row.last_error,
        "created_at": _dt(row.created_at),
    }


def serialize_post(row: CustomContentFactoryPost) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "platform": row.platform,
        "status": row.status,
        "external_id": row.external_id,
        "posted_url": row.posted_url,
        "caption_variant": row.caption_variant,
        "uniqualization_applied": row.uniqualization_applied or {},
        "views": int(row.views or 0),
        "likes": int(row.likes or 0),
        "comments": int(row.comments or 0),
        "shares": int(row.shares or 0),
        "saves": int(row.saves or 0),
        "hold_reason": row.hold_reason,
        "posted_at": _dt(row.posted_at),
        "analytics_synced_at": _dt(row.analytics_synced_at),
    }


def serialize_video(row: CustomContentFactoryVideo, include_posts: bool = True) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "status": row.status,
        "scheduled_for": _dt(row.scheduled_for),
        "started_at": _dt(row.started_at),
        "finished_at": _dt(row.finished_at),
        "idea": row.idea,
        "hook": row.hook,
        "script": row.script,
        "caption": row.caption,
        "hashtags": list(row.hashtags or []),
        "content_format": row.content_format,
        "visual_style": row.visual_style,
        "duration_seconds": int(row.duration_seconds or 0),
        "aspect_ratio": row.aspect_ratio,
        "video_url": row.video_url,
        "thumbnail_url": row.thumbnail_url,
        "storyboard": list(row.storyboard or []),
        "uniqualization": row.uniqualization or {},
        "uniqueness_hash": row.uniqueness_hash,
        "token_cost_usd": float(row.token_cost_usd or 0),
        "prompt_tokens": int(row.prompt_tokens or 0),
        "completion_tokens": int(row.completion_tokens or 0),
        "last_error": row.last_error,
        "preview": bool((row.extra or {}).get("preview")),
        "extra": {
            "preview": bool((row.extra or {}).get("preview")),
            "note": (row.extra or {}).get("note") or "",
            "clips": list((row.extra or {}).get("clips") or []),
            "clip_plan": list((row.extra or {}).get("clip_plan") or []),
            "clips_total": int((row.extra or {}).get("clips_total") or 0),
            "clips_done": int((row.extra or {}).get("clips_done") or 0),
            "stitched": bool((row.extra or {}).get("stitched")),
            "render_stage": (row.extra or {}).get("render_stage") or "",
            "hold_reason": (row.extra or {}).get("hold_reason") or "",
            "media_kind": (row.extra or {}).get("media_kind") or "video",
            "slide_urls": list((row.extra or {}).get("slide_urls") or []),
        },
        "created_at": _dt(row.created_at),
    }
    if include_posts:
        payload["posts"] = [serialize_post(item) for item in (row.posts or [])]
        payload["views"] = sum(int(item.views or 0) for item in (row.posts or []))
        payload["likes"] = sum(int(item.likes or 0) for item in (row.posts or []))
    return payload


async def list_accounts(session: AsyncSession, automation_id: int) -> list[CustomContentFactoryAccount]:
    result = await session.execute(
        select(CustomContentFactoryAccount)
        .where(CustomContentFactoryAccount.custom_automation_id == automation_id)
        .order_by(CustomContentFactoryAccount.created_at.desc())
    )
    return list(result.scalars().all())


def start_warmup(account: CustomContentFactoryAccount) -> None:
    now = now_utc()
    account.warmup_started_at = account.warmup_started_at or now
    account.warmup_completed_at = None
    account.status = "warming"
    account.updated_at = now


async def connect_account(
    session: AsyncSession,
    *,
    automation_id: int,
    platform: str,
    display_name: str,
    handle: str,
    external_id: str,
    credentials: dict[str, Any],
    start_warming: bool = True,
) -> CustomContentFactoryAccount:
    if platform not in PLATFORMS:
        raise ValueError(f"Неподдерживаемая площадка: {platform}")
    cleaned = validate_platform_credentials(platform, credentials, external_id=external_id)
    account = CustomContentFactoryAccount(
        custom_automation_id=automation_id,
        platform=platform,
        display_name=(display_name or handle or platform)[:200],
        handle=(handle or "")[:128],
        external_id=(external_id or cleaned.get("ig_user_id") or cleaned.get("open_id") or "")[:191],
        credentials_enc=encrypt_json(cleaned),
        status="warming" if start_warming else "connected",
        is_enabled=True,
        health_score=70,
        risk_flags=[],
        extra={},
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    if start_warming:
        start_warmup(account)
    session.add(account)
    await session.flush()
    return account


async def update_account(
    session: AsyncSession,
    *,
    automation_id: int,
    account_id: int,
    payload: dict[str, Any],
) -> CustomContentFactoryAccount:
    account = await session.get(CustomContentFactoryAccount, account_id)
    if not account or account.custom_automation_id != automation_id:
        raise ValueError("Аккаунт не найден")
    for field in ("display_name", "handle", "external_id"):
        if field in payload and payload[field] is not None:
            setattr(account, field, str(payload[field] or "")[:200])
    if "is_enabled" in payload and payload["is_enabled"] is not None:
        account.is_enabled = bool(payload["is_enabled"])
    credentials = payload.get("credentials")
    if isinstance(credentials, dict) and any(str(value or "").strip() for value in credentials.values()):
        merged = decrypt_json(account.credentials_enc)
        for key, value in credentials.items():
            if str(value or "").strip():
                merged[str(key)] = str(value).strip()
        account.credentials_enc = encrypt_json(merged)
    if payload.get("pause"):
        account.status = "paused"
    if payload.get("resume") and account.status == "paused":
        account.status = "ready" if account.warmup_completed_at else "warming"
    account.updated_at = now_utc()
    await session.flush()
    return account


async def delete_account(session: AsyncSession, *, automation_id: int, account_id: int) -> None:
    account = await session.get(CustomContentFactoryAccount, account_id)
    if not account or account.custom_automation_id != automation_id:
        raise ValueError("Аккаунт не найден")
    await session.delete(account)
    await session.flush()


async def list_videos(
    session: AsyncSession,
    automation_id: int,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CustomContentFactoryVideo], int]:
    filters = [CustomContentFactoryVideo.custom_automation_id == automation_id]
    if status:
        filters.append(CustomContentFactoryVideo.status == status)
    total = await session.scalar(select(func.count()).select_from(CustomContentFactoryVideo).where(*filters))
    result = await session.execute(
        select(CustomContentFactoryVideo)
        .options(selectinload(CustomContentFactoryVideo.posts))
        .where(*filters)
        .order_by(CustomContentFactoryVideo.created_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().unique().all()), int(total or 0)


async def get_video(session: AsyncSession, automation_id: int, video_id: int) -> CustomContentFactoryVideo:
    video = await session.scalar(
        select(CustomContentFactoryVideo)
        .options(selectinload(CustomContentFactoryVideo.posts))
        .where(
            CustomContentFactoryVideo.id == video_id,
            CustomContentFactoryVideo.custom_automation_id == automation_id,
        )
    )
    if not video:
        raise ValueError("Ролик не найден")
    return video


async def list_token_usage(
    session: AsyncSession,
    automation_id: int,
    *,
    limit: int = 50,
) -> list[CustomContentFactoryTokenUsage]:
    result = await session.execute(
        select(CustomContentFactoryTokenUsage)
        .where(CustomContentFactoryTokenUsage.custom_automation_id == automation_id)
        .order_by(CustomContentFactoryTokenUsage.created_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    return list(result.scalars().all())


async def record_token_usage(
    session: AsyncSession,
    *,
    automation_id: int,
    video_id: int | None,
    provider: str,
    model: str,
    operation: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
) -> CustomContentFactoryTokenUsage:
    row = CustomContentFactoryTokenUsage(
        custom_automation_id=automation_id,
        video_id=video_id,
        provider=provider,
        model=model or "",
        operation=operation,
        prompt_tokens=int(prompt_tokens or 0),
        completion_tokens=int(completion_tokens or 0),
        cost_usd=float(cost_usd or 0),
        created_at=now_utc(),
    )
    session.add(row)
    if video_id:
        video = await session.get(CustomContentFactoryVideo, video_id)
        if video:
            video.prompt_tokens = int(video.prompt_tokens or 0) + int(prompt_tokens or 0)
            video.completion_tokens = int(video.completion_tokens or 0) + int(completion_tokens or 0)
            video.token_cost_usd = float(video.token_cost_usd or 0) + float(cost_usd or 0)
    await session.flush()
    return row


async def dashboard_snapshot(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    settings = await get_or_create_settings(session, automation_id)
    accounts = await list_accounts(session, automation_id)
    posted = await session.scalar(
        select(func.count()).select_from(CustomContentFactoryPost).join(CustomContentFactoryVideo).where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryPost.status.in_(("posted", "sandbox")),
        )
    )
    in_flight = await session.scalar(
        select(func.count()).select_from(CustomContentFactoryVideo).where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryVideo.status.in_(tuple(VIDEO_IN_FLIGHT)),
        )
    )
    views = await session.scalar(
        select(func.coalesce(func.sum(CustomContentFactoryPost.views), 0))
        .select_from(CustomContentFactoryPost)
        .join(CustomContentFactoryVideo)
        .where(CustomContentFactoryVideo.custom_automation_id == automation_id)
    )
    likes = await session.scalar(
        select(func.coalesce(func.sum(CustomContentFactoryPost.likes), 0))
        .select_from(CustomContentFactoryPost)
        .join(CustomContentFactoryVideo)
        .where(CustomContentFactoryVideo.custom_automation_id == automation_id)
    )
    token_spend = await session.scalar(
        select(func.coalesce(func.sum(CustomContentFactoryTokenUsage.cost_usd), 0)).where(
            CustomContentFactoryTokenUsage.custom_automation_id == automation_id
        )
    )
    month_start = datetime(now_utc().year, now_utc().month, 1)
    token_month = await session.scalar(
        select(func.coalesce(func.sum(CustomContentFactoryTokenUsage.cost_usd), 0)).where(
            CustomContentFactoryTokenUsage.custom_automation_id == automation_id,
            CustomContentFactoryTokenUsage.created_at >= month_start,
        )
    )
    videos, _ = await list_videos(session, automation_id, limit=8, offset=0)
    warming = sum(1 for item in accounts if item.status == "warming")
    ready = sum(1 for item in accounts if item.status in {"ready", "connected"} and item.is_enabled)
    risk = sum(1 for item in accounts if item.status in {"shadow_risk", "restricted"})
    due_at = next_enqueue_at(last_enqueued_at=settings.last_enqueued_at, videos_per_day=settings.videos_per_day)
    return {
        "settings": serialize_settings(settings),
        "kpis": {
            "posted": int(posted or 0),
            "in_flight": int(in_flight or 0),
            "views": int(views or 0),
            "likes": int(likes or 0),
            "token_spend_usd": round(float(token_spend or 0), 4),
            "token_spend_month_usd": round(float(token_month or 0), 4),
            "accounts_total": len(accounts),
            "accounts_ready": ready,
            "accounts_warming": warming,
            "accounts_risk": risk,
        },
        "next_slot": {
            "at": _dt(due_at),
            "in_window": in_posting_window(
                timezone_name=settings.timezone,
                start=settings.posting_window_start,
                end=settings.posting_window_end,
            ),
            "sandbox_mode": bool(settings.sandbox_mode),
        },
        "readiness": build_readiness(settings, accounts),
        "accounts": [serialize_account(item, settings) for item in accounts],
        "recent_videos": [serialize_video(item) for item in videos],
    }


def build_readiness(
    settings: CustomContentFactorySettings,
    accounts: list[CustomContentFactoryAccount],
) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    product = (settings.product_name or "").strip()
    if len(product) < 2:
        items.append({
            "code": "product",
            "level": "block",
            "text": "Укажите название продукта в настройках — без брифа завод не стартует.",
        })
    if not (settings.audience or "").strip():
        items.append({
            "code": "audience",
            "level": "warn",
            "text": "Опишите аудиторию, чтобы сценарии попадали в тон.",
        })
    if not accounts:
        items.append({
            "code": "accounts",
            "level": "warn",
            "text": "Нет аккаунтов: ролик соберём, публиковать будет некуда.",
        })
    kling = decrypted_secret(settings, "kling_api_key") or (app_settings.KLING_API_KEY or "").strip()
    if (settings.video_model or "kling") == "kling" and not kling:
        items.append({
            "code": "kling",
            "level": "info",
            "text": "Нет ключа Kling — будет раскадровка. С ключом завод режет ролик на клипы по 8с и склеивает.",
        })
    elif (settings.video_model or "kling") == "kling" and kling:
        items.append({
            "code": "kling_stitch",
            "level": "info",
            "text": "Kling даёт до 8с на клип. Завод сгенерирует несколько кусков и склеит в целевую длительность.",
        })
    base = (app_settings.BASE_URL or "").rstrip("/")
    if not settings.sandbox_mode and accounts and (not base or "localhost" in base or "127.0.0.1" in base):
        items.append({
            "code": "public_url",
            "level": "warn",
            "text": "Для Instagram / TikTok / Pinterest нужен публичный BASE_URL, чтобы площадка скачала файл. YouTube заберёт локальный ролик сам.",
        })
    if (settings.video_model or "") in {"runway", "luma"}:
        items.append({
            "code": "renderer",
            "level": "info",
            "text": "Runway и Luma пока не подключены. Выберите Kling или раскадровку.",
        })
    if settings.sandbox_mode:
        items.append({
            "code": "sandbox",
            "level": "info",
            "text": "Песочница включена: в соцсети ничего не уходит.",
        })
    ready_live = False
    for account in accounts:
        progress = warmup_progress(
            started_at=account.warmup_started_at,
            completed_at=account.warmup_completed_at,
            actions_done=int(account.warmup_actions_done or 0),
            warmup_days=int(settings.warmup_days or 7),
            actions_per_day=int(settings.warmup_actions_per_day or 8),
        )
        if account.is_enabled and account.status in {"ready", "connected"} and progress.get("complete"):
            ready_live = True
            break
    if not settings.sandbox_mode and accounts and not ready_live:
        items.append({
            "code": "warmup",
            "level": "warn",
            "text": "Боевой режим, но нет прогретого аккаунта — посты будут ждать окончания прогрева.",
        })
    return {
        "items": items,
        "can_generate": not any(item["level"] == "block" for item in items),
        "can_go_live": bool(product) and bool(accounts),
    }


async def retry_video(session: AsyncSession, automation_id: int, video_id: int) -> CustomContentFactoryVideo:
    video = await get_video(session, automation_id, video_id)
    if video.status not in {"failed", "skipped"}:
        raise ValueError("Повторить можно только ошибочный или пропущенный ролик")
    extra = dict(video.extra or {})
    extra["retried_at"] = now_utc().isoformat()
    extra.pop("hold_reason", None)
    video.extra = extra
    video.last_error = None
    video.finished_at = None
    video.updated_at = now_utc()
    if video.script and video.hook:
        if video.video_url:
            video.status = "ready" if video.uniqueness_hash else "uniqualizing"
        else:
            video.status = "rendering"
            video.render_task_id = None
    else:
        video.status = "queued"
    await session.flush()
    return video


async def skip_video(session: AsyncSession, automation_id: int, video_id: int) -> CustomContentFactoryVideo:
    video = await get_video(session, automation_id, video_id)
    if video.status in {"posted"}:
        raise ValueError("Опубликованный ролик нельзя пропустить")
    video.status = "skipped"
    video.finished_at = now_utc()
    video.updated_at = now_utc()
    video.last_error = None
    await session.flush()
    return video


async def recent_warmup_events_map(
    session: AsyncSession,
    account_ids: list[int],
    *,
    per_account: int = 5,
) -> dict[int, list[CustomContentFactoryWarmupEvent]]:
    if not account_ids:
        return {}
    result = await session.execute(
        select(CustomContentFactoryWarmupEvent)
        .where(CustomContentFactoryWarmupEvent.account_id.in_(account_ids))
        .order_by(CustomContentFactoryWarmupEvent.created_at.desc())
        .limit(max(1, per_account) * len(account_ids))
    )
    grouped: dict[int, list[CustomContentFactoryWarmupEvent]] = {}
    for event in result.scalars().all():
        bucket = grouped.setdefault(event.account_id, [])
        if len(bucket) < per_account:
            bucket.append(event)
    return grouped


def recipes_for_video(video: CustomContentFactoryVideo, settings: CustomContentFactorySettings, platforms: list[str]) -> dict[str, Any]:
    seed = f"{video.id}:{video.hook}:{video.script}"
    if not settings.unique_per_platform:
        platforms = platforms[:1] or ["youtube"]
    return {
        platform: uniqualize_recipe(platform=platform, seed=seed, enabled=bool(settings.uniqualize_enabled))
        for platform in platforms
    }


async def recent_hooks(session: AsyncSession, automation_id: int, limit: int = 12) -> list[str]:
    result = await session.execute(
        select(CustomContentFactoryVideo.hook)
        .where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryVideo.hook != "",
        )
        .order_by(CustomContentFactoryVideo.created_at.desc())
        .limit(limit)
    )
    return [row[0] for row in result.all() if row[0]]


async def add_warmup_event(
    session: AsyncSession,
    account: CustomContentFactoryAccount,
    *,
    action_type: str,
    detail: str,
) -> CustomContentFactoryWarmupEvent:
    event = CustomContentFactoryWarmupEvent(
        account_id=account.id,
        action_type=action_type,
        result="ok",
        detail=detail,
        created_at=now_utc(),
    )
    session.add(event)
    account.warmup_actions_done = int(account.warmup_actions_done or 0) + 1
    account.updated_at = now_utc()
    await session.flush()
    return event


def reset_daily_counter(account: CustomContentFactoryAccount, today: date | None = None) -> None:
    day = today or now_utc().date()
    if account.posts_today_date != day:
        account.posts_today = 0
        account.posts_today_date = day
