"""Personal Telegram blogs: one generated post, fanned out to every account channel.

The channel is attached to the profile as Telegram's personal channel.
The account bio never gets a t.me link. The product lives in native posts.
"""
from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...alembic.models import AccountPool, CustomAutomation, PoolAccount, SocialAccount
from ...config import settings as app_settings
from ...utils.crypto import decrypt_token, encrypt_token
from .account_pacing import account_may_do_work, farm_overlap_active_hours
from .account_restriction import restriction_blocks_action

logger = logging.getLogger(__name__)

MOSCOW = ZoneInfo("Europe/Moscow")
THEMES = ("expert", "case", "blog", "reflection", "infographic")
IMAGE_THEMES = {"case", "infographic"}
THEME_LABELS = {
    "expert": "Эксперт",
    "case": "Кейс",
    "blog": "Блог",
    "reflection": "Размышление",
    "infographic": "Инфографика",
}
TEXT_PROVIDERS: dict[str, dict[str, Any]] = {
    "chatgpt": {
        "label": "ChatGPT",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"),
        "default_model": "gpt-4o-mini",
    },
    "claude": {
        "label": "Claude",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "models": ("claude-sonnet-4-5", "claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"),
        "default_model": "claude-sonnet-4-5",
    },
    "grok": {
        "label": "Grok",
        "kind": "openai",
        "base_url": "https://api.x.ai/v1",
        "models": ("grok-3-mini", "grok-3", "grok-2-latest"),
        "default_model": "grok-3-mini",
    },
    "deepseek": {
        "label": "DeepSeek",
        "kind": "openai",
        "base_url": "https://api.deepseek.com",
        "models": ("deepseek-chat", "deepseek-reasoner"),
        "default_model": "deepseek-chat",
    },
}
IMAGE_PROVIDERS: dict[str, dict[str, Any]] = {
    "chatgpt": {
        "label": "ChatGPT",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": ("gpt-image-1", "dall-e-3"),
        "default_model": "gpt-image-1",
    },
    "grok": {
        "label": "Grok",
        "kind": "openai",
        "base_url": "https://api.x.ai/v1",
        "models": ("grok-2-image",),
        "default_model": "grok-2-image",
    },
}
_SECRET_SKIP = {
    "channels",
    "posts",
    "logs",
    "slots",
    "day_key",
    "avatar_path",
    "text_api_key",
    "image_api_key",
    "text_api_key_enc",
    "image_api_key_enc",
    "clear_text_api_key",
    "clear_image_api_key",
}
_JSON_BLOCK = re.compile(r"\{.*\}", re.S)
_MAX_POSTS = 30
_MAX_LOGS = 40
_SENDS_PER_PASS = 6


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_int_list(raw: Any) -> list[int]:
    items: list[int] = []
    seen: set[int] = set()
    for value in raw or []:
        try:
            ident = int(value)
        except (TypeError, ValueError):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ident)
    return items


def default_neuroblog_settings() -> dict[str, Any]:
    return {
        "account_ids": [],
        "channel_title": "Заметки",
        "channel_about": "Личные заметки о работе.",
        "style": "живой разговорный, от первого лица, без канцелярита",
        "posts_per_day": 2,
        "themes": list(THEMES),
        "product_name": "",
        "product_url": "",
        "prompt": "",
        "text_provider": "deepseek",
        "text_model": "deepseek-chat",
        "text_api_key_enc": "",
        "image_provider": "",
        "image_model": "",
        "image_api_key_enc": "",
        "require_proxy": False,
        "hide_in_work": False,
        "avatar_path": "",
        "channels": {},
        "posts": [],
        "day_key": "",
        "slots": [],
        "logs": [],
        "enabled": False,
    }


def _is_new_secret(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.startswith("••••") or set(text) <= {"•", "*"}:
        return False
    return True


def _store_secret(value: str) -> str:
    return encrypt_token(value.strip())


def _read_secret(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return decrypt_token(text).strip()
    except Exception:
        return ""


def _secret_hint(secret: str) -> str:
    if not secret:
        return ""
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"••••{tail}"


def _env_key_for(provider: str) -> str:
    if provider == "chatgpt":
        return (app_settings.OPENAI_API_KEY or "").strip()
    if provider == "deepseek":
        return (app_settings.DEEPSEEK_API_KEY or "").strip()
    if provider == "grok":
        return (getattr(app_settings, "XAI_API_KEY", "") or "").strip()
    return ""


def infer_text_provider(model: str, explicit: str = "") -> str:
    if explicit in TEXT_PROVIDERS:
        return explicit
    name = str(model or "").strip().lower()
    if name.startswith("claude"):
        return "claude"
    if name.startswith("grok"):
        return "grok"
    if name.startswith("gpt") or name.startswith("o1") or name.startswith("chatgpt") or name.startswith("dall"):
        return "chatgpt"
    return "deepseek"


def infer_image_provider(model: str, explicit: Any = None) -> str:
    if explicit == "":
        if str(model or "") in {"dall-e-3", "gpt-image-1"}:
            return "chatgpt"
        return ""
    if explicit in IMAGE_PROVIDERS:
        return str(explicit)
    name = str(model or "").strip().lower()
    if name in {"dall-e-3", "gpt-image-1"} or name.startswith("gpt-image"):
        return "chatgpt"
    if "grok" in name:
        return "grok"
    return ""


def _pick_model(provider: str, requested: str, catalog: dict[str, dict[str, Any]]) -> str:
    spec = catalog.get(provider) or {}
    models = tuple(spec.get("models") or ())
    name = str(requested or "").strip()
    if name and (name in models or not models):
        return name
    return str(spec.get("default_model") or (models[0] if models else name))


def _merge_secret(incoming: dict[str, Any], stored: dict[str, Any], plain_key: str, enc_key: str) -> str:
    if incoming.get(f"clear_{plain_key}"):
        return ""
    if _is_new_secret(incoming.get(plain_key)):
        return _store_secret(str(incoming.get(plain_key)))
    previous = str(stored.get(enc_key) or "")
    if previous:
        return previous
    leftover = stored.get(plain_key)
    if _is_new_secret(leftover):
        return _store_secret(str(leftover))
    return ""


def resolved_text_key(cfg: dict[str, Any]) -> tuple[str, str]:
    user_key = _read_secret(cfg.get("text_api_key_enc"))
    if user_key:
        return user_key, "user"
    env_key = _env_key_for(str(cfg.get("text_provider") or ""))
    if env_key:
        return env_key, "server"
    return "", "missing"


def resolved_image_key(cfg: dict[str, Any]) -> tuple[str, str]:
    provider = str(cfg.get("image_provider") or "")
    if not provider:
        return "", "off"
    user_key = _read_secret(cfg.get("image_api_key_enc"))
    if user_key:
        return user_key, "user"
    if provider == str(cfg.get("text_provider") or ""):
        shared, source = resolved_text_key(cfg)
        if shared:
            return shared, source
    env_key = _env_key_for(provider)
    if env_key:
        return env_key, "server"
    return "", "missing"


def bio_mentions_channel(about: str, stored: dict[str, Any] | None) -> bool:
    return strip_channel_from_bio(about, stored) != " ".join(str(about or "").split())


def strip_channel_from_bio(about: str, stored: dict[str, Any] | None) -> str:
    text = str(about or "")
    payload = stored if isinstance(stored, dict) else {}
    username = str(payload.get("username") or "").strip().lstrip("@")
    link = str(payload.get("link") or "").strip().rstrip("/")
    needles: list[str] = []
    if link:
        needles.extend([link, link.replace("https://", ""), link.replace("http://", "")])
    if username:
        needles.extend(
            [
                f"https://t.me/{username}",
                f"http://t.me/{username}",
                f"t.me/{username}",
                f"@{username}",
            ]
        )
    for needle in needles:
        if needle:
            text = re.sub(re.escape(needle), " ", text, flags=re.I)
    return " ".join(text.split())


def catalog_payload() -> dict[str, Any]:
    return {
        "themes": [{"id": key, "label": label} for key, label in THEME_LABELS.items()],
        "text_providers": [
            {
                "id": key,
                "label": spec["label"],
                "models": [{"id": item, "label": item} for item in spec["models"]],
                "images": key in IMAGE_PROVIDERS,
            }
            for key, spec in TEXT_PROVIDERS.items()
        ],
        "image_providers": [
            {
                "id": key,
                "label": spec["label"],
                "models": [{"id": item, "label": item} for item in spec["models"]],
            }
            for key, spec in IMAGE_PROVIDERS.items()
        ],
    }


def public_neuroblog_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    data = {key: value for key, value in cfg.items() if key not in _SECRET_SKIP}
    text_key, text_source = resolved_text_key(cfg)
    image_key, image_source = resolved_image_key(cfg)
    data["text_api_key_set"] = text_source == "user"
    data["text_api_key_hint"] = _secret_hint(text_key) if text_source == "user" else ""
    data["text_key_source"] = text_source
    data["image_api_key_set"] = image_source == "user"
    data["image_api_key_hint"] = _secret_hint(image_key) if image_source == "user" else ""
    data["image_key_source"] = image_source
    data["avatar_uploaded"] = bool(cfg.get("avatar_path"))
    return data


def neuroblog_issues(cfg: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not cfg.get("account_ids"):
        issues.append("Выберите аккаунты, у которых появится личный канал")
    _key, source = resolved_text_key(cfg)
    if source == "missing":
        label = TEXT_PROVIDERS.get(str(cfg.get("text_provider") or ""), {}).get("label") or "модели"
        issues.append(f"Укажите API-ключ для {label}")
    if str(cfg.get("image_provider") or "") and resolved_image_key(cfg)[1] == "missing":
        issues.append("Для картинок укажите API-ключ ChatGPT или Grok")
    return issues


def neuroblog_notices(cfg: dict[str, Any]) -> list[str]:
    notices: list[str] = []
    if resolved_text_key(cfg)[1] == "server":
        notices.append("Свой ключ не сохранён — текст пойдёт через серверный ключ выбранного провайдера")
    if IMAGE_THEMES.intersection(cfg.get("themes") or []) and not cfg.get("image_provider"):
        notices.append("Кейс и инфографика уйдут без картинки, пока не подключите ChatGPT или Grok")
    return notices


def normalize_neuroblog_settings(raw: Any, *, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    base = default_neuroblog_settings()
    stored = previous if isinstance(previous, dict) else {}
    incoming = raw if isinstance(raw, dict) else {}
    skip_overlay = _SECRET_SKIP | {"posts", "slots", "logs", "day_key", "channels", "avatar_path"}
    data = {
        **base,
        **stored,
        **{key: value for key, value in incoming.items() if key in base and key not in skip_overlay},
    }
    data["account_ids"] = _as_int_list(incoming.get("account_ids", stored.get("account_ids")))
    data["channel_title"] = (
        str(incoming.get("channel_title", stored.get("channel_title") or base["channel_title"])).strip()[:128] or "Заметки"
    )
    data["channel_about"] = str(incoming.get("channel_about", stored.get("channel_about") or "")).strip()[:255]
    data["style"] = str(incoming.get("style", stored.get("style") or base["style"])).strip()[:400]
    try:
        per_day = int(incoming.get("posts_per_day", stored.get("posts_per_day") or 2))
    except (TypeError, ValueError):
        per_day = 2
    data["posts_per_day"] = max(1, min(5, per_day))
    themes = [
        str(item)
        for item in (incoming.get("themes") if "themes" in incoming else stored.get("themes") or [])
        if str(item) in THEMES
    ]
    data["themes"] = themes or list(THEMES)
    data["product_name"] = str(incoming.get("product_name", stored.get("product_name") or "")).strip()[:120]
    data["product_url"] = str(incoming.get("product_url", stored.get("product_url") or "")).strip()[:300]
    data["prompt"] = str(incoming.get("prompt", stored.get("prompt") or "")).strip()[:4000]
    provider = infer_text_provider(
        str(incoming.get("text_model", stored.get("text_model") or "")),
        str(incoming.get("text_provider", stored.get("text_provider") or "")).strip(),
    )
    data["text_provider"] = provider
    data["text_model"] = _pick_model(provider, str(incoming.get("text_model", stored.get("text_model") or "")), TEXT_PROVIDERS)
    image_model = str(incoming.get("image_model", stored.get("image_model") or "")).strip()
    image_provider = infer_image_provider(
        image_model,
        incoming.get("image_provider") if "image_provider" in incoming else stored.get("image_provider"),
    )
    data["image_provider"] = image_provider
    data["image_model"] = _pick_model(image_provider, image_model, IMAGE_PROVIDERS) if image_provider else ""
    data["text_api_key_enc"] = _merge_secret(incoming, stored, "text_api_key", "text_api_key_enc")
    data["image_api_key_enc"] = _merge_secret(incoming, stored, "image_api_key", "image_api_key_enc")
    data["require_proxy"] = bool(incoming.get("require_proxy", stored.get("require_proxy", False)))
    data["hide_in_work"] = bool(incoming.get("hide_in_work", stored.get("hide_in_work", False)))
    data["avatar_path"] = str(stored.get("avatar_path") or incoming.get("avatar_path") or "")[:512]
    data["channels"] = stored.get("channels") if isinstance(stored.get("channels"), dict) else {}
    data["posts"] = list(stored.get("posts") or [])[-_MAX_POSTS:]
    data["day_key"] = str(stored.get("day_key") or "")
    data["slots"] = list(stored.get("slots") or [])
    data["logs"] = list(stored.get("logs") or [])[-_MAX_LOGS:]
    data["enabled"] = bool(incoming.get("enabled", stored.get("enabled", False)))
    data.pop("text_api_key", None)
    data.pop("image_api_key", None)
    return data


def image_needed(theme: str, requested: bool = True) -> bool:
    """Pictures only for cases and infographics. A diary post stays text."""
    return bool(requested) and str(theme) in IMAGE_THEMES


def parse_post_draft(raw: str) -> dict[str, Any]:
    match = _JSON_BLOCK.search(raw or "")
    blob = match.group(0) if match else (raw or "")
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    theme = str(data.get("theme") or "blog").strip().lower()
    if theme not in THEMES:
        theme = "blog"
    text = " ".join(str(data.get("text") or "").split())
    prompt = " ".join(str(data.get("image_prompt") or "").split())
    return {
        "theme": theme,
        "text": text[:3500],
        "needs_image": image_needed(theme, bool(data.get("needs_image", True))),
        "image_prompt": prompt[:800] if image_needed(theme, True) else "",
    }


def plan_day_slots(
    *,
    day_key: str,
    count: int,
    start_hour: int,
    end_hour: int,
    seed: int,
) -> list[str]:
    """Random UTC timestamps inside the Moscow work window."""
    year, month, day = (int(part) for part in day_key.split("-"))
    start = datetime(year, month, day, max(0, start_hour), 15, tzinfo=MOSCOW)
    end = datetime(year, month, day, min(23, max(start_hour + 1, end_hour - 1)), 30, tzinfo=MOSCOW)
    span = max(60.0, (end - start).total_seconds())
    rng = random.Random(seed)
    picks = sorted(start + timedelta(seconds=rng.uniform(0, span)) for _ in range(max(1, count)))
    return [item.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="minutes") for item in picks]


def due_slot(slots: list[str], posts_today: int, *, now: datetime | None = None) -> bool:
    current = now or _utc_now()
    if posts_today >= len(slots):
        return False
    try:
        when = datetime.fromisoformat(slots[posts_today])
    except ValueError:
        return False
    return when <= current


def _moscow_day(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(MOSCOW).date().isoformat()


def _append_log(cfg: dict[str, Any], message: str) -> None:
    logs = list(cfg.get("logs") or [])
    logs.append({"at": _utc_now().isoformat(timespec="minutes"), "message": message[:400]})
    cfg["logs"] = logs[-_MAX_LOGS:]


def _load_cfg(automation: CustomAutomation) -> dict[str, Any]:
    blob = automation.module_settings or {}
    raw = blob.get("neuroblog") if isinstance(blob, dict) else {}
    return normalize_neuroblog_settings(raw, previous=raw if isinstance(raw, dict) else {})


def _store_cfg(automation: CustomAutomation, cfg: dict[str, Any]) -> None:
    blob = dict(automation.module_settings or {})
    blob["neuroblog"] = cfg
    automation.module_settings = blob
    flag_modified(automation, "module_settings")


def _account_row(account: SocialAccount, pool: PoolAccount, channel: dict[str, Any]) -> dict[str, Any]:
    from .account_roles import account_is_task_ready
    from .proxy_service import proxy_label
    from .rotation_service import current_daily_messages_sent

    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    attached = bool(channel.get("personal_attached"))
    return {
        "id": account.id,
        "label": account.display_name or account.username or account.phone_number or f"#{account.id}",
        "display_name": account.display_name,
        "username": account.username,
        "phone_number": account.phone_number,
        "warmup_status": pool.warmup_status or "idle",
        "proxy_label": proxy_label(getattr(account, "telegram_proxy", None)),
        "has_proxy": bool(account.telegram_proxy or pool.proxy_id),
        "is_active": bool(account.is_active),
        "is_banned": bool(account.is_banned),
        "is_frozen": bool(account.is_frozen),
        "is_spamblocked": bool(account.is_spamblocked),
        "is_channel_banned": bool(account.is_channel_banned),
        "in_work": in_work,
        "daily_messages_sent": current_daily_messages_sent(account),
        "eligible": account_is_task_ready(pool, account, "neuroblog"),
        "channel_title": channel.get("title") or "",
        "channel_attached": attached,
        "channel_status": "attached" if attached else ("created" if channel.get("id") else "none"),
    }


async def get_neuroblog_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    cfg = _load_cfg(automation)
    pairs = (
        await session.execute(
            select(SocialAccount, PoolAccount)
            .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
            .join(AccountPool, PoolAccount.account_pool_id == AccountPool.id)
            .where(PoolAccount.custom_automation_id == automation_id, AccountPool.is_default.is_(True))
            .order_by(SocialAccount.id.asc())
            .limit(300)
        )
    ).all()
    channels = cfg.get("channels") or {}
    accounts = [_account_row(account, pool, channels.get(str(account.id)) or {}) for account, pool in pairs]
    attached = sum(1 for item in accounts if item.get("id") in set(cfg.get("account_ids") or []) and item.get("channel_attached"))
    return {
        "enabled": bool(cfg.get("enabled")),
        "settings": public_neuroblog_settings(cfg),
        "accounts": accounts,
        "channels": [
            {
                "account_id": int(key),
                "title": value.get("title") or "",
                "attached": bool(value.get("personal_attached")),
                "status": "attached" if value.get("personal_attached") else "created",
            }
            for key, value in channels.items()
            if str(key).isdigit() and isinstance(value, dict)
        ],
        "posts": list(reversed(cfg.get("posts") or []))[:12],
        "logs": list(reversed(cfg.get("logs") or []))[:20],
        "next_slots": list(cfg.get("slots") or []),
        "issues": neuroblog_issues(cfg),
        "notices": neuroblog_notices(cfg),
        "summary": {
            "accounts": len(cfg.get("account_ids") or []),
            "attached": attached,
            "posts_today": _posts_today(cfg),
            "posts_per_day": int(cfg.get("posts_per_day") or 1),
        },
        **catalog_payload(),
    }


async def save_neuroblog_module(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    current = _load_cfg(automation)
    incoming = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    cfg = normalize_neuroblog_settings(incoming, previous=current)
    if payload.get("enabled") is not None:
        cfg["enabled"] = bool(payload.get("enabled"))
    elif "enabled" in incoming:
        cfg["enabled"] = bool(incoming.get("enabled"))
    else:
        cfg["enabled"] = bool(current.get("enabled"))
    _store_cfg(automation, cfg)
    await session.commit()
    return await get_neuroblog_module(session, automation_id)


async def save_neuroblog_avatar(session: AsyncSession, automation_id: int, filename: str, content: bytes) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    suffix = Path(filename or "avatar.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    folder = Path(app_settings.MEDIA_ROOT).resolve() / "neuroblog" / str(automation_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"avatar{suffix}"
    path.write_bytes(content)
    cfg = _load_cfg(automation)
    cfg["avatar_path"] = str(path.relative_to(Path(app_settings.MEDIA_ROOT).resolve())).replace("\\", "/")
    for item in (cfg.get("channels") or {}).values():
        if isinstance(item, dict):
            item["avatar_set"] = False
    _append_log(cfg, "Обновил аватарку канала")
    _store_cfg(automation, cfg)
    await session.commit()
    return await get_neuroblog_module(session, automation_id)


def _work_hours() -> tuple[int, int]:
    from .work_mode import current_work_mode

    mode = current_work_mode()
    return int(mode["hour_start"]), int(mode["hour_end"])


def _refresh_slots(cfg: dict[str, Any], automation_id: int) -> None:
    day = _moscow_day()
    if cfg.get("day_key") == day and cfg.get("slots"):
        return
    start, end = _work_hours()
    cfg["day_key"] = day
    cfg["slots"] = plan_day_slots(
        day_key=day,
        count=int(cfg.get("posts_per_day") or 1),
        start_hour=start,
        end_hour=end,
        seed=automation_id * 1000 + int(day.replace("-", "")),
    )


def _posts_today(cfg: dict[str, Any]) -> int:
    day = cfg.get("day_key") or _moscow_day()
    return sum(1 for item in cfg.get("posts") or [] if str(item.get("day") or "") == day)


def _open_post(cfg: dict[str, Any], account_ids: list[int]) -> dict[str, Any] | None:
    for item in reversed(cfg.get("posts") or []):
        sent = {int(value) for value in (item.get("sent") or [])}
        if any(account_id not in sent for account_id in account_ids):
            if item.get("day") == (cfg.get("day_key") or _moscow_day()):
                return item
    return None


def _channel_needs_setup(account: SocialAccount, cfg: dict[str, Any]) -> bool:
    stored = (cfg.get("channels") or {}).get(str(account.id))
    if not isinstance(stored, dict) or not stored.get("id"):
        return True
    if not stored.get("personal_attached"):
        return True
    if stored.get("bio_set"):
        return True
    if cfg.get("avatar_path") and not stored.get("avatar_set"):
        return True
    if cfg.get("channel_about") and stored.get("about") != cfg.get("channel_about"):
        return True
    if cfg.get("channel_title") and stored.get("title") != cfg.get("channel_title"):
        return True
    return False


async def _complete_text(cfg: dict[str, Any], prompt: str) -> str:
    import httpx
    from openai import AsyncOpenAI

    provider = str(cfg.get("text_provider") or "deepseek")
    spec = TEXT_PROVIDERS.get(provider) or TEXT_PROVIDERS["deepseek"]
    api_key, source = resolved_text_key(cfg)
    if not api_key:
        raise RuntimeError("no_text_api_key")
    model = str(cfg.get("text_model") or spec["default_model"])
    logger.info("Neuroblog text via %s/%s", provider, source)
    if spec.get("kind") == "anthropic":
        async with httpx.AsyncClient(timeout=60.0) as http:
            response = await http.post(
                f"{spec['base_url']}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 900,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
        return "".join(
            str(part.get("text") or "")
            for part in (payload.get("content") or [])
            if part.get("type") == "text"
        )
    client = AsyncOpenAI(api_key=api_key, base_url=spec["base_url"], timeout=60.0, max_retries=0)
    result = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
        temperature=0.8,
    )
    return result.choices[0].message.content or ""


async def _generate_draft(cfg: dict[str, Any]) -> dict[str, Any]:
    previous = [
        f"{index + 1}. [{item.get('theme')}] {item.get('text')}"
        for index, item in enumerate((cfg.get("posts") or [])[-6:])
    ]
    themes = ", ".join(THEME_LABELS.get(item, item) for item in cfg.get("themes") or THEMES)
    instructions = f"""
Сгенерируй один пост для личного Telegram-канала.
Стилистика: {cfg.get("style") or "живой текст"}.
Допустимые темы: {themes}. Выбери одну.
Продукт упоминай нативно и редко, только если уместно: {cfg.get("product_name") or "не задан"}.
Ссылка на продукт, если упоминаешь: {cfg.get("product_url") or "нет"}.
Дополнительные указания: {cfg.get("prompt") or "нет"}.
Предыдущие посты, можно сослаться если уместно:
{chr(10).join(previous) or "пока нет"}
Картинка нужна только для кейса или инфографики (график, схема, цифры). Для блога и размышлений needs_image=false.
Ответ строго JSON: {{"theme":"expert|case|blog|reflection|infographic","text":"...","needs_image":false,"image_prompt":""}}
""".strip()
    return parse_post_draft(await _complete_text(cfg, instructions))


async def _generate_image(cfg: dict[str, Any], prompt: str, automation_id: int) -> str:
    from openai import AsyncOpenAI

    provider = str(cfg.get("image_provider") or "")
    spec = IMAGE_PROVIDERS.get(provider)
    api_key, _source = resolved_image_key(cfg)
    if not prompt or not spec or not api_key:
        return ""
    client = AsyncOpenAI(api_key=api_key, base_url=spec["base_url"], timeout=90.0, max_retries=0)
    model = str(cfg.get("image_model") or spec["default_model"])
    try:
        result = await client.images.generate(model=model, prompt=prompt[:900], size="1024x1024", n=1)
    except Exception:
        result = await client.images.generate(model=model, prompt=prompt[:900], n=1)
    data = (result.data or [None])[0]
    raw = getattr(data, "b64_json", None)
    folder = Path(app_settings.MEDIA_ROOT).resolve() / "neuroblog" / str(automation_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"post-{int(_utc_now().timestamp())}.png"
    if raw:
        import base64

        path.write_bytes(base64.b64decode(raw))
        return str(path)
    url = getattr(data, "url", None)
    if not url:
        return ""
    import httpx

    async with httpx.AsyncClient(timeout=40.0) as http:
        response = await http.get(url)
        response.raise_for_status()
        path.write_bytes(response.content)
    return str(path)


async def _resolve_channel(raw: Any, stored: dict[str, Any]) -> Any | None:
    from telethon.tl.types import InputPeerChannel

    try:
        access = int(stored.get("access_hash") or 0)
        if stored.get("id") and access:
            return await raw.get_entity(InputPeerChannel(int(stored["id"]), access))
        if stored.get("username"):
            return await raw.get_entity(stored["username"])
        if stored.get("id"):
            return await raw.get_entity(int(stored["id"]))
    except Exception as exc:
        logger.info("Neuroblog channel resolve failed: %s", exc)
    return None


async def _clear_channel_link_from_bio(client: Any, raw: Any, stored: dict[str, Any]) -> None:
    from telethon.tl.functions.users import GetFullUserRequest

    about = ""
    try:
        me = await raw.get_me()
        full = await raw(GetFullUserRequest(me))
        about = getattr(getattr(full, "full_user", None), "about", None) or ""
    except Exception as exc:
        logger.info("Neuroblog bio read skipped: %s", exc)
        about = ""
    if not stored.get("bio_set") and not bio_mentions_channel(about, stored):
        return
    cleaned = strip_channel_from_bio(about, stored)
    if cleaned == " ".join(str(about or "").split()) and not stored.get("bio_set"):
        return
    try:
        await client.set_bio(cleaned)
        stored["bio_set"] = False
        stored["bio_cleared"] = True
    except Exception as exc:
        logger.info("Neuroblog bio clear skipped: %s", exc)


async def _ensure_channel(account: SocialAccount, cfg: dict[str, Any]) -> dict[str, Any]:
    from telethon.tl.functions.account import UpdatePersonalChannelRequest
    from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest, EditTitleRequest
    from telethon.tl.functions.messages import EditChatAboutRequest
    from telethon.tl.types import InputChatUploadedPhoto
    from telethon.utils import get_input_channel

    from .telegram_account_client import TelegramAccountClient

    stored = dict((cfg.get("channels") or {}).get(str(account.id)) or {})
    title = str(cfg.get("channel_title") or "Заметки")[:128]
    about = str(cfg.get("channel_about") or "")[:255]
    async with TelegramAccountClient.for_account(account) as client:
        raw = client.client
        channel = await _resolve_channel(raw, stored) if stored.get("id") else None
        if channel is None:
            created = await raw(CreateChannelRequest(title=title, about=about, broadcast=True, megagroup=False))
            channel = created.chats[0]
            username = str(getattr(channel, "username", None) or "")
            stored = {
                "id": int(getattr(channel, "id")),
                "access_hash": int(getattr(channel, "access_hash", 0) or 0),
                "username": username,
                "link": f"https://t.me/{username}" if username else "",
                "title": title,
                "about": about,
                "personal_attached": False,
                "bio_set": False,
            }
        if title and stored.get("title") != title:
            try:
                await raw(EditTitleRequest(channel, title))
                stored["title"] = title
            except Exception as exc:
                logger.info("Neuroblog title skipped for %s: %s", account.id, exc)
        if about and stored.get("about") != about:
            try:
                await raw(EditChatAboutRequest(channel, about))
                stored["about"] = about
            except Exception as exc:
                logger.info("Neuroblog about skipped for %s: %s", account.id, exc)
        avatar = str(cfg.get("avatar_path") or "")
        if avatar and not stored.get("avatar_set"):
            file_path = Path(app_settings.MEDIA_ROOT).resolve() / avatar
            if file_path.exists():
                uploaded = await raw.upload_file(str(file_path))
                await raw(EditPhotoRequest(channel, InputChatUploadedPhoto(uploaded)))
                stored["avatar_set"] = True
        if not stored.get("personal_attached"):
            try:
                await raw(UpdatePersonalChannelRequest(get_input_channel(channel)))
                stored["personal_attached"] = True
            except Exception as exc:
                stored["personal_attached"] = False
                logger.info("Neuroblog personal channel skipped for %s: %s", account.id, exc)
        await _clear_channel_link_from_bio(client, raw, stored)
    cfg.setdefault("channels", {})[str(account.id)] = stored
    return stored


async def _send_post(account: SocialAccount, channel: dict[str, Any], text: str, image_path: str) -> None:
    from telethon.tl.types import InputPeerChannel

    from .telegram_account_client import TelegramAccountClient

    async with TelegramAccountClient.for_account(account) as client:
        access = int(channel.get("access_hash") or 0)
        if channel.get("id") and access:
            entity: Any = InputPeerChannel(int(channel["id"]), access)
        else:
            entity = channel.get("username") or int(channel["id"])
        kwargs: dict[str, Any] = {}
        if image_path and Path(image_path).exists():
            kwargs["file"] = image_path
        await client.client.send_message(entity, text[:1024] if kwargs else text[:3500], **kwargs)


async def run_neuroblog_pass(automation_id: int, *, force: bool = False) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "missing"}
        from .work_mode import apply_work_mode, reset_work_mode

        token = apply_work_mode(automation)
        try:
            cfg = _load_cfg(automation)
            if not cfg.get("enabled") and not force:
                return {"status": "skipped", "reason": "disabled"}
            if not force and not farm_overlap_active_hours():
                return {"status": "skipped", "reason": "night"}
            account_ids = list(cfg.get("account_ids") or [])
            if not account_ids:
                return {"status": "skipped", "reason": "no_accounts"}
            if resolved_text_key(cfg)[1] == "missing":
                _append_log(cfg, "Нет API-ключа текстовой модели")
                _store_cfg(automation, cfg)
                await session.commit()
                return {"status": "skipped", "reason": "no_text_key"}
            _refresh_slots(cfg, automation_id)
            accounts = (
                await session.execute(select(SocialAccount).where(SocialAccount.id.in_(account_ids)))
            ).scalars().all()
            by_id = {account.id: account for account in accounts}
            ready = [
                account
                for account in (by_id.get(item) for item in account_ids)
                if account is not None
                and account.is_active
                and not account.is_banned
                and account_may_do_work(account)
                and not restriction_blocks_action(account, "neuroblog")
            ]
            if not ready:
                _store_cfg(automation, cfg)
                await session.commit()
                return {"status": "skipped", "reason": "nobody_ready"}
            setups = 0
            for account in ready:
                if setups >= 3:
                    break
                if not _channel_needs_setup(account, cfg):
                    continue
                try:
                    channel = await _ensure_channel(account, cfg)
                    status = "прикрепил как личный" if channel.get("personal_attached") else "создал, жду прикрепления"
                    _append_log(cfg, f"Канал аккаунта {account.id}: {status}")
                except Exception as exc:
                    _append_log(cfg, f"Не собрал канал для {account.id}: {exc}")
                    logger.warning("Neuroblog channel failed for %s: %s", account.id, exc)
                setups += 1
            open_post = _open_post(cfg, [account.id for account in ready])
            created = False
            if open_post is None and (force or due_slot(cfg.get("slots") or [], _posts_today(cfg))):
                try:
                    draft = await _generate_draft(cfg)
                except Exception as exc:
                    _append_log(cfg, f"Текст не собрал: {exc}")
                    draft = {"text": ""}
                if not draft.get("text"):
                    _append_log(cfg, "Модель вернула пустой пост")
                else:
                    image_path = ""
                    if draft["needs_image"] and cfg.get("image_provider"):
                        try:
                            image_path = await _generate_image(cfg, draft.get("image_prompt") or "", automation_id)
                        except Exception as exc:
                            _append_log(cfg, f"Картинку не собрал: {exc}")
                    open_post = {
                        "day": cfg["day_key"],
                        "at": _utc_now().isoformat(timespec="minutes"),
                        "theme": draft["theme"],
                        "text": draft["text"],
                        "image_prompt": draft.get("image_prompt") or "",
                        "image_path": image_path,
                        "sent": [],
                    }
                    cfg.setdefault("posts", []).append(open_post)
                    cfg["posts"] = cfg["posts"][-_MAX_POSTS:]
                    created = True
                    _append_log(cfg, f"Собрал пост «{THEME_LABELS.get(draft['theme'], draft['theme'])}»")
            sent = 0
            if open_post is not None:
                already = {int(value) for value in open_post.get("sent") or []}
                for account in ready:
                    if sent >= _SENDS_PER_PASS:
                        break
                    if account.id in already:
                        continue
                    channel = (cfg.get("channels") or {}).get(str(account.id))
                    if not channel or not channel.get("id"):
                        continue
                    try:
                        await _send_post(account, channel, open_post["text"], open_post.get("image_path") or "")
                        already.add(account.id)
                        sent += 1
                    except Exception as exc:
                        _append_log(cfg, f"Не отправил в канал {account.id}: {exc}")
                        logger.warning("Neuroblog send failed for %s: %s", account.id, exc)
                open_post["sent"] = sorted(already)
            _store_cfg(automation, cfg)
            await session.commit()
            return {"status": "ok", "created": created, "sent": sent}
        finally:
            reset_work_mode(token)


def neuroblog_scheduler_active(automation: CustomAutomation | None) -> bool:
    if automation is None:
        return False
    blob = getattr(automation, "module_settings", None) or {}
    return bool((blob.get("neuroblog") or {}).get("enabled"))
