"""Anti-shadowban helpers for the custom content factory."""
from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


PLATFORMS = ("youtube", "instagram", "pinterest", "tiktok")

CONTENT_FORMATS = (
    "educational",
    "direct_ad",
    "motion",
    "storytelling",
    "ugc",
    "mixed",
)

VISUAL_STYLES = ("animation", "realism", "motion", "mixed")

WARMUP_ACTIONS = (
    ("watch_niche", "Просмотр роликов в своей нише"),
    ("like_native", "Лайки на живой контент, не свой"),
    ("browse_feed", "Лента без публикаций"),
    ("save_reference", "Сохранения референсов"),
    ("profile_polish", "Правка шапки и сторис-обложки"),
    ("comment_light", "Короткий комментарий без ссылок"),
)

HOOK_PREFIXES = (
    "стоп",
    "подожди",
    "смотри",
    "вот почему",
    "не покупай",
    "если ты",
    "за 30 секунд",
    "правда в том",
    "большинство",
    "никто не говорит",
    "ошибка",
    "секрет",
    "wait",
    "stop",
    "don't",
    "if you",
)

VIDEO_IN_FLIGHT = {
    "queued",
    "ideating",
    "scripting",
    "rendering",
    "uniqualizing",
    "ready",
    "posting",
}

VIDEO_TERMINAL = {"posted", "failed", "skipped", "sandbox"}

PLATFORM_CREDENTIAL_HINTS = {
    "youtube": "refresh_token или access_token",
    "instagram": "access_token и Instagram User ID",
    "tiktok": "access_token Content Posting API",
    "pinterest": "access_token и board_id",
}


def now_utc() -> datetime:
    return datetime.utcnow()


def parse_hhmm(value: str) -> tuple[int, int]:
    raw = str(value or "09:00").strip()
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", raw)
    if not match:
        return 9, 0
    return int(match.group(1)), int(match.group(2))


def local_now(timezone_name: str) -> datetime:
    try:
        zone = ZoneInfo(str(timezone_name or "Europe/Moscow"))
    except Exception:
        zone = ZoneInfo("Europe/Moscow")
    return datetime.now(zone)


def in_posting_window(*, timezone_name: str, start: str, end: str, moment: datetime | None = None) -> bool:
    current = moment or local_now(timezone_name)
    start_h, start_m = parse_hhmm(start)
    end_h, end_m = parse_hhmm(end)
    minutes = current.hour * 60 + current.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    if start_minutes == end_minutes:
        return True
    if start_minutes < end_minutes:
        return start_minutes <= minutes < end_minutes
    return minutes >= start_minutes or minutes < end_minutes


def jitter_post_time(moment: datetime, *, avoid_exact_hour: bool) -> datetime:
    shifted = moment + timedelta(minutes=random.randint(3, 17), seconds=random.randint(5, 50))
    if avoid_exact_hour and shifted.minute < 4:
        shifted += timedelta(minutes=random.randint(6, 14))
    if avoid_exact_hour and shifted.minute > 56:
        shifted -= timedelta(minutes=random.randint(6, 14))
    return shifted.replace(tzinfo=None) if shifted.tzinfo else shifted


def enqueue_interval_hours(videos_per_day: float) -> float:
    per_day = max(0.2, min(float(videos_per_day or 1), 8.0))
    return 24.0 / per_day


def is_due(*, last_enqueued_at: datetime | None, videos_per_day: float, now: datetime | None = None) -> bool:
    current = now or now_utc()
    if last_enqueued_at is None:
        return True
    hours = enqueue_interval_hours(videos_per_day)
    return current >= last_enqueued_at + timedelta(hours=hours)


def warmup_required_actions(warmup_days: int, actions_per_day: int) -> int:
    days = max(1, min(int(warmup_days or 7), 30))
    per_day = max(2, min(int(actions_per_day or 8), 20))
    return days * per_day


def warmup_progress(*, started_at: datetime | None, completed_at: datetime | None, actions_done: int, warmup_days: int, actions_per_day: int, now: datetime | None = None) -> dict[str, Any]:
    current = now or now_utc()
    required = warmup_required_actions(warmup_days, actions_per_day)
    if completed_at:
        return {
            "complete": True,
            "percent": 100,
            "actions_done": max(actions_done, required),
            "actions_required": required,
            "days_left": 0,
        }
    if not started_at:
        return {
            "complete": False,
            "percent": 0,
            "actions_done": 0,
            "actions_required": required,
            "days_left": max(1, int(warmup_days or 7)),
        }
    elapsed = max(0.0, (current - started_at).total_seconds())
    needed_seconds = max(1, int(warmup_days or 7)) * 86400
    time_ratio = min(1.0, elapsed / needed_seconds)
    action_ratio = min(1.0, max(0, actions_done) / float(required))
    ratio = min(time_ratio, action_ratio)
    days_left = max(0, int(warmup_days or 7) - int(elapsed // 86400))
    complete = ratio >= 1.0
    return {
        "complete": complete,
        "percent": int(round(ratio * 100)),
        "actions_done": actions_done,
        "actions_required": required,
        "days_left": 0 if complete else days_left,
    }


def can_post_from_account(
    *,
    status: str,
    is_enabled: bool,
    warmup: dict[str, Any],
    posts_today: int,
    max_posts_per_day: int,
    last_posted_at: datetime | None,
    stagger_min_minutes: int,
    now: datetime | None = None,
) -> tuple[bool, str]:
    if not is_enabled:
        return False, "Аккаунт выключен"
    if status in {"paused", "restricted", "shadow_risk", "disconnected"}:
        return False, f"Статус аккаунта: {status}"
    if not warmup.get("complete"):
        return False, "Прогрев ещё не закончен"
    if posts_today >= max(1, int(max_posts_per_day or 1)):
        return False, "Дневной лимит постов исчерпан"
    current = now or now_utc()
    if last_posted_at:
        wait = timedelta(minutes=max(5, int(stagger_min_minutes or 25)))
        if current < last_posted_at + wait:
            return False, "Слишком рано после прошлого поста"
    return True, ""


def hook_is_strong(hook: str) -> bool:
    text = re.sub(r"\s+", " ", str(hook or "")).strip()
    if len(text) < 12 or len(text) > 180:
        return False
    lowered = text.lower()
    if any(prefix in lowered for prefix in HOOK_PREFIXES):
        return True
    if text.endswith("?") or "!" in text[:24]:
        return True
    return bool(re.search(r"\d", text)) and len(text.split()) <= 18


def caption_variant(
    base: str,
    platform: str,
    product_url: str,
    seed: str,
    hashtags: list[str] | None = None,
) -> str:
    text = re.sub(r"\s+", " ", str(base or "")).strip()
    suffixes = {
        "youtube": "Подпишись, если хочешь ещё разборы.",
        "instagram": "Сохрани, чтобы не потерять.",
        "tiktok": "Досмотри до хука — там суть.",
        "pinterest": "Идея, которую можно внедрить сегодня.",
    }
    extra = suffixes.get(platform, "")
    url = str(product_url or "").strip()
    parts = [text]
    if extra and extra.lower() not in text.lower():
        parts.append(extra)
    if url and url not in text:
        if platform in {"youtube", "pinterest"}:
            parts.append(url)
        else:
            parts.append("Ссылка в профиле.")
    tags: list[str] = []
    for raw in hashtags or []:
        clean = re.sub(r"[^\w]+", "", str(raw).lstrip("#"), flags=re.UNICODE)
        if clean:
            tags.append(f"#{clean[:40]}")
    unique_tags = list(dict.fromkeys(tags))[:8]
    if unique_tags:
        parts.append(" ".join(unique_tags))
    variant = " ".join(part for part in parts if part).strip()
    if len(variant) > 2100:
        variant = variant[:2097] + "..."
    return variant


def uniqualize_recipe(*, platform: str, seed: str, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {"platform": platform, "passthrough": True}
    digest = hashlib.sha256(f"{seed}:{platform}:uniq".encode("utf-8")).digest()
    speed = 0.97 + (digest[0] / 255.0) * 0.06
    crop = 0.8 + (digest[1] / 255.0) * 2.4
    temp = -180 + int(digest[2] / 255.0 * 360)
    pitch = -12 + int(digest[3] / 255.0 * 24)
    shift_ms = 40 + int(digest[4] / 255.0 * 220)
    return {
        "platform": platform,
        "speed": round(speed, 3),
        "crop_pct": round(crop, 2),
        "color_temp": temp,
        "audio_pitch_cents": pitch,
        "intro_frame_shift_ms": shift_ms,
        "grain": bool(digest[5] % 2),
        "mirror_safe": platform != "youtube",
        "audio_duck_db": round(0.4 + (digest[6] / 255.0) * 1.4, 2),
    }


def uniqueness_hash(*, script: str, hook: str, recipes: dict[str, Any]) -> str:
    payload = f"{script}|{hook}|{recipes}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def pick_warmup_action(seed: str) -> tuple[str, str]:
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    return WARMUP_ACTIONS[digest[0] % len(WARMUP_ACTIONS)]


def should_flag_shadowban(*, recent_posts: list[dict[str, Any]], threshold: int, now: datetime | None = None) -> bool:
    current = now or now_utc()
    cutoff = current - timedelta(hours=30)
    zero = [
        post
        for post in recent_posts
        if post.get("status") in {"posted", "sandbox"}
        and post.get("posted_at")
        and post["posted_at"] <= cutoff
        and int(post.get("views") or 0) == 0
    ]
    return len(zero) >= max(2, int(threshold or 3))


def should_clear_shadowban(*, recent_posts: list[dict[str, Any]]) -> bool:
    live = [post for post in recent_posts if post.get("status") == "posted"][:3]
    if not live:
        return False
    return sum(int(post.get("views") or 0) for post in live) > 0


def compute_health_score(
    *,
    status: str,
    warmup_complete: bool,
    last_error: str | None,
    risk_flags: list[str] | None,
    recent_views: int = 0,
) -> int:
    score = 78
    if status == "warming":
        score -= 8
    elif status == "shadow_risk":
        score -= 28
    elif status == "restricted":
        score -= 40
    elif status == "paused":
        score -= 12
    elif status == "disconnected":
        score -= 50
    if not warmup_complete:
        score -= 6
    if last_error:
        score -= 10
    if "shadowban" in (risk_flags or []):
        score -= 8
    if recent_views >= 50:
        score += 8
    elif recent_views > 0:
        score += 3
    return max(1, min(100, score))


def next_enqueue_at(*, last_enqueued_at: datetime | None, videos_per_day: float, now: datetime | None = None) -> datetime:
    current = now or now_utc()
    if last_enqueued_at is None:
        return current
    due = last_enqueued_at + timedelta(hours=enqueue_interval_hours(videos_per_day))
    return due if due > current else current


def warmup_action_interval(actions_per_day: int) -> timedelta:
    per_day = max(2, min(int(actions_per_day or 8), 20))
    return timedelta(hours=24.0 / per_day)


def validate_platform_credentials(
    platform: str,
    credentials: dict[str, Any] | None,
    *,
    external_id: str = "",
) -> dict[str, str]:
    name = str(platform or "").strip().lower()
    if name not in PLATFORMS:
        raise ValueError(f"Неподдерживаемая площадка: {platform}")
    cleaned = {
        str(key): str(value).strip()
        for key, value in (credentials or {}).items()
        if str(value or "").strip()
    }
    if name == "youtube":
        if not cleaned.get("refresh_token") and not cleaned.get("access_token"):
            raise ValueError("YouTube: нужен refresh_token или access_token")
    elif name == "instagram":
        user_id = cleaned.get("ig_user_id") or str(external_id or "").strip()
        if not cleaned.get("access_token") or not user_id:
            raise ValueError("Instagram: нужны access_token и Instagram User ID")
        cleaned["ig_user_id"] = user_id
    elif name == "tiktok":
        if not cleaned.get("access_token"):
            raise ValueError("TikTok: нужен access_token")
    elif name == "pinterest":
        if not cleaned.get("access_token") or not cleaned.get("board_id"):
            raise ValueError("Pinterest: нужны access_token и board_id")
    return cleaned


def factory_return_url(return_url: str | None, automation_id: int, *, base_url: str = "") -> str:
    from urllib.parse import urlparse

    path = f"/custom/automations/{automation_id}/content-factory"
    fallback = f"{(base_url or '').rstrip('/')}{path}/accounts"
    if not return_url:
        return fallback
    parsed = urlparse(str(return_url).strip())
    if parsed.scheme not in {"http", "https"}:
        return fallback
    if path not in (parsed.path or ""):
        return fallback
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def estimate_llm_cost_usd(*, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    name = str(model or "").lower()
    if "gpt-4o" in name:
        inp, out = 2.5, 10.0
    elif "claude" in name:
        inp, out = 3.0, 15.0
    elif "deepseek" in name:
        inp, out = 0.14, 0.28
    else:
        inp, out = 0.5, 1.5
    return round((prompt_tokens / 1_000_000) * inp + (completion_tokens / 1_000_000) * out, 6)


def estimate_render_cost_usd(*, video_model: str, duration_seconds: int) -> float:
    name = str(video_model or "").lower()
    seconds = max(8, int(duration_seconds or 30))
    if "kling" in name:
        per_sec = 0.012
    elif "runway" in name:
        per_sec = 0.05
    elif "luma" in name:
        per_sec = 0.04
    elif "veo" in name:
        per_sec = 0.08
    else:
        per_sec = 0.0
    return round(seconds * per_sec, 4)
