"""Autonomous idea → render → uniqualize → post loop."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...alembic.database import async_session_maker
from ...alembic.models import (
    CustomContentFactoryAccount,
    CustomContentFactoryPost,
    CustomContentFactorySettings,
    CustomContentFactoryVideo,
    CustomContentFactoryWarmupEvent,
)
from ...config import settings as app_settings
from ...services.kling_client import KlingClient
from .content_factory_antifraud import (
    CONTENT_FORMATS,
    VIDEO_IN_FLIGHT,
    VISUAL_STYLES,
    can_post_from_account,
    caption_variant,
    compute_health_score,
    estimate_llm_cost_usd,
    estimate_render_cost_usd,
    hook_is_strong,
    in_posting_window,
    is_due,
    jitter_post_time,
    live_daily_cap,
    local_midnight_utc_naive,
    now_utc,
    parse_utc_naive,
    pick_media_kind,
    pick_warmup_action,
    publish_attempt_due,
    PUBLISH_ATTEMPT_LIMIT,
    settle_publish_status,
    should_clear_shadowban,
    should_flag_shadowban,
    uniqueness_hash,
    warmup_action_interval,
    warmup_progress,
)
from .content_factory_media import (
    align_storyboard,
    clip_prompt,
    concat_clips,
    download_to_file,
    generate_grok_authoring,
    generate_grok_carousel_pack,
    generate_slide_png,
    factory_grok_bot_id,
    local_path_from_url,
    mix_soundtrack,
    plan_clip_durations,
    public_media_url,
    slides_to_mp4,
    synthesize_voiceover,
    uniqualize_file,
    video_dir,
    voiceover_lines,
    write_music_bed,
    write_thumbnail,
)
from .content_factory_proxy import PROXY_MISSING, proxy_url_for_account
from .content_factory_publishers import (
    PublisherError,
    fetch_post_analytics,
    merge_platform_credentials,
    publish_to_platform,
)
from .content_factory_service import (
    add_warmup_event,
    decrypt_json,
    decrypted_secret,
    encrypt_json,
    get_or_create_settings,
    recent_hooks,
    recipes_for_video,
    record_token_usage,
    reset_daily_counter,
)

KLING_POLL_LIMIT = 80
PROCESSING_TIMEOUT = timedelta(hours=6)

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def factory_scheduler_active(automation) -> bool:
    blob = getattr(automation, "module_settings", None) or {}
    if bool((blob.get("content_factory") or {}).get("enabled")):
        return True
    return False


async def run_content_factory_pass(automation_id: int) -> dict[str, Any]:
    async with async_session_maker() as session:
        result = await tick(session, automation_id)
        await session.commit()
        return result


async def tick(session: AsyncSession, automation_id: int, *, force_enqueue: bool = False) -> dict[str, Any]:
    settings = await get_or_create_settings(session, automation_id)
    warmup = 0
    shadow = 0
    enqueued = None
    synced = 0
    if settings.enabled:
        warmup = await _advance_warmup(session, automation_id, settings)
        shadow = await _apply_shadowban_guards(session, automation_id, settings)
        if force_enqueue or (settings.product_name or "").strip():
            enqueued = await _enqueue_if_due(session, automation_id, settings, force=force_enqueue)
        synced = await _sync_analytics(session, automation_id)
    processed = await _process_next_video(session, automation_id, settings)
    return {
        "warmup_events": warmup,
        "shadowban_flags": shadow,
        "enqueued_video_id": enqueued.id if enqueued else None,
        "processed_video_id": processed.id if processed else None,
        "processed_status": processed.status if processed else None,
        "analytics_synced": synced,
        "skipped": None if settings.enabled else "disabled",
    }


async def generate_now(session: AsyncSession, automation_id: int) -> CustomContentFactoryVideo:
    settings = await get_or_create_settings(session, automation_id)
    if len((settings.product_name or "").strip()) < 2:
        raise ValueError("Сначала укажите продукт в настройках контент-завода")
    video = await _enqueue_if_due(session, automation_id, settings, force=True)
    if video is None:
        raise ValueError("Не удалось поставить ролик в очередь")
    kling_waits = 0
    for _ in range(80):
        current = await session.get(CustomContentFactoryVideo, video.id)
        if not current or current.status in {"posted", "failed", "skipped", "sandbox"}:
            break
        before = current.status
        await _advance_video(session, current, settings)
        await session.flush()
        awaiting = bool((current.extra or {}).get("awaiting_kling"))
        if current.status == "rendering" and awaiting:
            kling_waits += 1
            if kling_waits > 40:
                break
            await asyncio.sleep(2)
            continue
        kling_waits = 0
        if before in {"ready", "posting"} and current.status == "ready":
            break
        if current.status in {"ready", "posting"} and not settings.sandbox_mode:
            if current.scheduled_for and current.scheduled_for > now_utc():
                break
    refreshed = await session.get(CustomContentFactoryVideo, video.id)
    return refreshed or video


async def _enqueue_if_due(
    session: AsyncSession,
    automation_id: int,
    settings: CustomContentFactorySettings,
    *,
    force: bool = False,
) -> CustomContentFactoryVideo | None:
    queued_count = int(
        await session.scalar(
            select(func.count()).select_from(CustomContentFactoryVideo).where(
                CustomContentFactoryVideo.custom_automation_id == automation_id,
                CustomContentFactoryVideo.status.in_(tuple(VIDEO_IN_FLIGHT)),
            )
        )
        or 0
    )
    if queued_count >= 5 and not force:
        return None
    if not force and not (settings.product_name or "").strip():
        return None
    if not force and not is_due(last_enqueued_at=settings.last_enqueued_at, videos_per_day=settings.videos_per_day):
        return None
    scheduled = now_utc() if force else jitter_post_time(now_utc(), avoid_exact_hour=bool(settings.avoid_exact_hour))
    formats = list(settings.content_formats or ["educational"])
    styles = list(settings.visual_styles or ["realism"])
    duration = random.randint(int(settings.duration_min or 30), max(int(settings.duration_min or 30), int(settings.duration_max or 45)))
    share = int(getattr(settings, "carousel_share", 0) or 0)
    if share and not _carousel_key(settings)[2]:
        share = 0
    media_kind = pick_media_kind(share, random.randint(1, 100))
    video = CustomContentFactoryVideo(
        custom_automation_id=automation_id,
        status="queued",
        scheduled_for=scheduled,
        content_format=random.choice(formats if formats else ["educational"]),
        visual_style=random.choice(styles if styles else ["realism"]),
        duration_seconds=duration,
        aspect_ratio=settings.aspect_ratio or "9:16",
        hashtags=[],
        storyboard=[],
        uniqualization={},
        extra={"media_kind": media_kind},
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(video)
    settings.last_enqueued_at = now_utc()
    settings.updated_at = now_utc()
    await session.flush()
    return video


def _has_processing_posts(video: CustomContentFactoryVideo) -> bool:
    return any(getattr(post, "status", None) == "processing" for post in (video.posts or []))


def _publish_time_blocked(video: CustomContentFactoryVideo, settings: CustomContentFactorySettings) -> bool:
    """True when a new publish should wait. Platform polling still runs."""
    if settings.sandbox_mode or _has_processing_posts(video):
        return False
    if video.scheduled_for and video.scheduled_for > now_utc():
        return True
    manual = bool((video.extra or {}).get("manual"))
    if not manual and not in_posting_window(
        timezone_name=settings.timezone,
        start=settings.posting_window_start,
        end=settings.posting_window_end,
    ):
        return True
    nxt = parse_utc_naive(str((video.extra or {}).get("next_publish_at") or ""))
    return bool(nxt and nxt > now_utc())


async def _claim_video(session: AsyncSession, video: CustomContentFactoryVideo) -> bool:
    """Compare-and-set on Postgres so two app instances do not advance the same row."""
    connection = await session.connection()
    if connection.dialect.name != "postgresql":
        return True
    seen_at = video.updated_at
    now = now_utc()
    result = await session.execute(
        update(CustomContentFactoryVideo)
        .where(
            CustomContentFactoryVideo.id == video.id,
            CustomContentFactoryVideo.status == video.status,
            CustomContentFactoryVideo.updated_at == seen_at,
        )
        .values(updated_at=now)
    )
    if int(result.rowcount or 0) != 1:
        return False
    video.updated_at = now
    return True


async def _load_inflight(
    session: AsyncSession,
    automation_id: int,
    *,
    limit: int = 8,
) -> list[CustomContentFactoryVideo]:
    result = await session.execute(
        select(CustomContentFactoryVideo)
        .options(selectinload(CustomContentFactoryVideo.posts))
        .where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryVideo.status.in_(tuple(VIDEO_IN_FLIGHT)),
        )
        .order_by(CustomContentFactoryVideo.scheduled_for.asc(), CustomContentFactoryVideo.id.asc())
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def _process_next_video(
    session: AsyncSession,
    automation_id: int,
    settings: CustomContentFactorySettings,
) -> CustomContentFactoryVideo | None:
    """Advance generation even while an older video is waiting to publish."""
    videos = await _load_inflight(session, automation_id)
    if not videos:
        return None
    generation = next((item for item in videos if item.status not in {"ready", "posting"}), None)
    publishing = next((item for item in videos if item.status in {"ready", "posting"}), None)
    progressed: CustomContentFactoryVideo | None = None
    heavy_render = generation is not None and generation.status == "uniqualizing"
    if generation is not None and await _claim_video(session, generation):
        await _advance_video(session, generation, settings)
        progressed = generation
    if publishing is not None and publishing is not generation and not heavy_render:
        if _publish_time_blocked(publishing, settings):
            return progressed or publishing
        if await _claim_video(session, publishing):
            await _advance_video(session, publishing, settings)
            progressed = publishing
    return progressed or videos[0]


async def _advance_video(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    try:
        if bool((video.extra or {}).get("manual")):
            if video.status in {"ready", "posting"}:
                await _post_video(session, video, settings)
            video.updated_at = now_utc()
            return
        if video.status in {"queued", "ideating", "scripting"} and _is_grok_carousel(video, settings):
            await _render_carousel(session, video, settings)
        elif video.status == "queued":
            await _write_idea_and_script(session, video, settings)
        elif video.status in {"ideating", "scripting"}:
            await _write_idea_and_script(session, video, settings)
        elif video.status == "rendering":
            kind = str((video.extra or {}).get("media_kind") or "")
            if kind == "carousel" and not _carousel_key(settings)[2]:
                extra = dict(video.extra or {})
                extra["media_kind"] = "video"
                extra["carousel_skipped"] = "no_image_key"
                video.extra = extra
                kind = "video"
            if kind == "carousel":
                await _render_carousel(session, video, settings)
            else:
                await _render_video(session, video, settings)
        elif video.status == "uniqualizing":
            await _uniqualize(session, video, settings)
        elif video.status in {"ready", "posting"}:
            await _post_video(session, video, settings)
        video.updated_at = now_utc()
    except Exception as exc:
        logger.exception("Content factory video %s failed: %s", video.id, exc)
        video.status = "failed"
        video.last_error = str(exc)[:800]
        video.finished_at = now_utc()
        video.updated_at = now_utc()


async def _write_idea_and_script(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    video.status = "scripting"
    video.started_at = video.started_at or now_utc()
    used = await recent_hooks(session, video.custom_automation_id)
    performance = await _performance_hint(session, video.custom_automation_id)
    pack = await _generate_pack(settings, video, used, performance)
    hook = str(pack.get("hook") or "").strip()
    authored_by_grok = str((pack.get("usage") or {}).get("provider") or "") == "grok"
    if settings.hook_required and not hook_is_strong(hook) and not authored_by_grok:
        hook = _fallback_hook(settings, video.id)
    video.idea = str(pack.get("idea") or "")[:2000]
    video.hook = hook[:300]
    video.script = _compose_script(hook, str(pack.get("script") or ""), settings)
    video.caption = str(pack.get("caption") or video.idea)[:2000]
    video.hashtags = [str(tag).lstrip("#")[:40] for tag in (pack.get("hashtags") or []) if str(tag).strip()][:12]
    durations = plan_clip_durations(int(video.duration_seconds or 30))
    video.storyboard = align_storyboard(list(pack.get("storyboard") or []), durations)
    extra = dict(video.extra or {})
    extra["clip_durations"] = durations
    extra["clips_total"] = len(durations)
    extra["clips_done"] = 0
    video.extra = extra
    video.content_format = str(pack.get("content_format") or video.content_format)
    video.visual_style = str(pack.get("visual_style") or video.visual_style)
    if pack.get("usage"):
        usage = pack["usage"]
        cost = estimate_llm_cost_usd(
            model=str(usage.get("model") or settings.script_model),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        )
        await record_token_usage(
            session,
            automation_id=video.custom_automation_id,
            video_id=video.id,
            provider=str(usage.get("provider") or "llm"),
            model=str(usage.get("model") or settings.script_model),
            operation="script",
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=cost,
        )
    video.status = "rendering"
    video.last_error = None


def _compose_script(hook: str, body: str, settings: CustomContentFactorySettings) -> str:
    text = body.strip()
    if hook and hook.lower() not in text.lower()[:180]:
        text = f"{hook}\n\n{text}".strip()
    cta = (settings.cta_text or "").strip()
    url = (settings.product_url or "").strip()
    if cta and cta.lower() not in text.lower():
        text = f"{text}\n\n{cta}" + (f" {url}" if url else "")
    elif url and url not in text:
        text = f"{text}\n\n{url}"
    return text[:8000]


async def _performance_hint(session: AsyncSession, automation_id: int) -> str:
    result = await session.execute(
        select(
            CustomContentFactoryVideo.hook,
            CustomContentFactoryPost.platform,
            CustomContentFactoryPost.views,
            CustomContentFactoryPost.likes,
        )
        .join(CustomContentFactoryPost, CustomContentFactoryPost.video_id == CustomContentFactoryVideo.id)
        .where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryPost.status == "posted",
        )
        .order_by(CustomContentFactoryPost.views.desc(), CustomContentFactoryPost.posted_at.desc())
        .limit(4)
    )
    lines = []
    for hook, platform, views, likes in result.all():
        lines.append(f"{platform}: {int(views or 0)} просмотров, {int(likes or 0)} лайков — {str(hook or '')[:80]}")
    if not lines:
        return ""
    return "Уже опубликованное, от сильного к слабому. Угол сильных можно развить, текст не копировать:\n" + "\n".join(lines)


async def _generate_pack(
    settings: CustomContentFactorySettings,
    video: CustomContentFactoryVideo,
    used_hooks: list[str],
    performance: str = "",
) -> dict[str, Any]:
    prompt = _authoring_prompt(settings, video, used_hooks, performance)
    carousel = str((video.extra or {}).get("media_kind") or "") == "carousel"
    if _script_author_is_grok(settings):
        grok_key = _xai_key(settings)
        if not grok_key:
            raise RuntimeError("Grok выбран автором сценария, но ключа нет")
        try:
            author = await generate_grok_authoring(
                api_key=grok_key,
                message=f"{_creative_system(carousel)}\n\n{prompt}",
                previous_response_id=str(getattr(settings, "grok_bot_response_id", "") or ""),
            )
        except Exception as exc:
            logger.info("Content factory grok bot did not return a script")
            detail = str(exc).strip()
            if detail and "sk-" not in detail and "xai-" not in detail and "bearer" not in detail.lower():
                raise RuntimeError(detail[:300]) from None
            raise RuntimeError("Grok-бот не отдал сценарий") from None
        if author and author.get("response_id"):
            settings.grok_bot_response_id = str(author["response_id"])[:2000]
            settings.updated_at = now_utc()
        pack = _pack_from_grok(_parse_json_object((author or {}).get("text") if author else ""), video)
        if pack is None:
            raise RuntimeError("Grok-бот не отдал разборный сценарий")
        return pack
    fallback = _fallback_pack(settings, video, used_hooks)
    completion = await _llm_json(
        settings,
        system_prompt=_creative_system(carousel),
        user_prompt=prompt,
        model=settings.script_model or settings.idea_model,
    )
    if not completion:
        return fallback
    data, usage = completion
    merged = {**fallback, **{key: data[key] for key in data if data.get(key)}}
    merged["usage"] = usage
    if merged.get("content_format") not in CONTENT_FORMATS:
        merged["content_format"] = video.content_format
    if merged.get("visual_style") not in VISUAL_STYLES:
        merged["visual_style"] = video.visual_style
    if not isinstance(merged.get("storyboard"), list) or not merged["storyboard"]:
        merged["storyboard"] = fallback["storyboard"]
    return merged


GROK_SCRIPT_MODEL = "grok-4.7"


def _script_author_is_grok(settings: CustomContentFactorySettings) -> bool:
    model = str(getattr(settings, "script_model", "") or "").strip().lower()
    if not model:
        model = str(getattr(settings, "idea_model", "") or "").strip().lower()
    return "grok" in model


def _pack_from_grok(data: dict[str, Any] | None, video: CustomContentFactoryVideo) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    board = data.get("storyboard")
    if not isinstance(board, list):
        return None
    scenes = []
    for item in board:
        if not isinstance(item, dict):
            continue
        visual = str(item.get("visual") or "").strip()
        voice = str(item.get("voiceover") or "").strip()
        if not visual and not voice:
            continue
        scene = {"visual": visual, "voiceover": voice}
        if item.get("t") is not None:
            scene["t"] = item.get("t")
        if item.get("duration") is not None:
            scene["duration"] = item.get("duration")
        scenes.append(scene)
    if not scenes:
        return None
    hook = str(data.get("hook") or "").strip()
    script = str(data.get("script") or "").strip()
    idea = str(data.get("idea") or "").strip()
    if not (hook or script or idea):
        return None
    content_format = data.get("content_format")
    if content_format not in CONTENT_FORMATS:
        content_format = video.content_format
    visual_style = data.get("visual_style")
    if visual_style not in VISUAL_STYLES:
        visual_style = video.visual_style
    tags = data.get("hashtags") if isinstance(data.get("hashtags"), list) else []
    return {
        "idea": idea or hook or script,
        "hook": hook or idea or script,
        "script": script or hook or idea,
        "caption": str(data.get("caption") or "").strip() or hook or idea,
        "hashtags": tags,
        "storyboard": scenes,
        "content_format": content_format,
        "visual_style": visual_style,
        "usage": {
            "provider": "grok",
            "model": GROK_SCRIPT_MODEL,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        },
    }


def _xai_key(settings: CustomContentFactorySettings) -> str:
    key = decrypted_secret(settings, "xai_api_key") if hasattr(settings, "xai_api_key_enc") else ""
    return (key or (getattr(app_settings, "XAI_API_KEY", "") or "")).strip()


def _parse_json_object(text: str | None) -> dict[str, Any] | None:
    match = _JSON_BLOCK.search(str(text or "").strip())
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _creative_system(carousel: bool) -> str:
    from .creative_voice import LIVING_VOICE, NEWS_PEG, SATIRE_SHOT

    kind = "фото-карусели для Instagram, TikTok и Pinterest" if carousel else "вертикального ролика 30–60 секунд"
    return (
        f"Ты автор {kind}. Креатив обыгрывает новость ниши, а не рассказывает о продукте из вакуума.\n"
        f"{LIVING_VOICE}\n{NEWS_PEG}\n{SATIRE_SHOT}\n"
        "Верни только JSON."
    )


def _authoring_prompt(
    settings: CustomContentFactorySettings,
    video: CustomContentFactoryVideo,
    used_hooks: list[str],
    performance: str = "",
) -> str:
    from .creative_voice import tone_line

    voice = (
        f"Продукт: {settings.product_name or 'сервис'}\n"
        f"Описание: {settings.product_description}\n"
        f"Аудитория: {settings.audience}\n"
        f"Ниша: {settings.niche}\n"
        f"Формат: {video.content_format}; картинка: {video.visual_style}; язык: {settings.language}\n"
        f"Тон: {tone_line(settings.tone)}\n"
        f"Голос: {settings.brand_voice or 'как человек из ниши, не как бренд'}\n"
        f"Нельзя: {settings.forbidden_topics or 'гарантии дохода, фейковые отзывы, выдуманные цифры'}\n"
        "Сначала выбери один новостной повод ниши. idea — в чём шутка или мысль. "
        "hook — первая фраза уже про этот повод. script и voiceover рассуждают о нём, продукт всплывает побочно.\n"
        "visual каждой сцены — английский промпт одного кадра: та же физика новости, другой нелепый объект. "
        "Без текста на изображении и без логотипов.\n"
        f"Не повторяй хуки: {used_hooks[:8]}\n"
        f"{performance}\n"
    )
    if str((video.extra or {}).get("media_kind") or "") == "carousel":
        return (
            voice
            + "Пять кадров 9:16. Instagram, TikTok и Pinterest получают фото-карусель. YouTube и VK Клипы — то же как слайд-шоу с музыкой.\n"
            "Кадр 1 — объект новости. Кадр 2–4 — подмена и сравнение. Кадр 5 — панч, не призыв купить.\n"
            "JSON: idea, hook, script, caption, hashtags (массив), storyboard "
            "(ровно 5 объектов {visual, voiceover}), content_format, visual_style. "
            "voiceover — короткая живая подпись кадра, можно разговорный мат."
        )
    durations = plan_clip_durations(int(video.duration_seconds or 30))
    starts = []
    cursor = 0
    for length in durations:
        starts.append(cursor)
        cursor += length
    return (
        voice
        + f"Длительность: {sum(durations)}с, кадр {video.aspect_ratio}.\n"
        + f"Клипы по 5–8с, склейка: {durations}. Старт сцен: {starts}.\n"
        + "Первая секунда — уже событие, не вопрос в пустоту.\n"
        + f"storyboard — ровно {len(durations)} сцен под клипы, один и тот же объект и свет.\n"
        + "JSON: idea, hook, script, caption, hashtags (массив), storyboard "
        + "(массив {t, duration, visual, voiceover}), content_format, visual_style."
    )


def _fallback_hook(settings: CustomContentFactorySettings, nonce: int) -> str:
    product = settings.product_name or "этот сервис"
    templates = [
        f"Стоп. {product} закрывает рутину, которую вы всё ещё делаете руками.",
        f"Если вы продаёте {settings.niche or 'продукт'} — первые 3 секунды решают, останется ли зритель.",
        f"Не покупай рекламу, пока не увидишь, как {product} собирает прогрев сам.",
        f"Вот почему холодный аккаунт сжигает охваты, а {product} их копит.",
        f"За {settings.duration_min or 30} секунд разберём воронку, которую вы продаёте вслепую.",
    ]
    return templates[nonce % len(templates)]


def _fallback_pack(
    settings: CustomContentFactorySettings,
    video: CustomContentFactoryVideo,
    used_hooks: list[str],
) -> dict[str, Any]:
    hook = _fallback_hook(settings, video.id + len(used_hooks))
    product = settings.product_name or "продукт"
    idea = (
        f"{video.content_format}: короткий ролик про {product} для аудитории "
        f"{settings.audience or 'тех, кто ищет рабочий инструмент'}."
    )
    script = (
        f"{hook}\n"
        f"Проблема: аудитория не доверяет прямой рекламе и скроллит.\n"
        f"Сцена: показываем боль → простой приём → как {product} закрывает её без крика.\n"
        f"Финал: конкретный следующий шаг.{(' ' + settings.cta_text) if (settings.cta_text or '').strip() else ''}"
    )
    cta_voice = (settings.cta_text or "").strip() or "Спокойный следующий шаг без крика."
    durations = plan_clip_durations(int(video.duration_seconds or 30))
    visuals = [
        "Крупный хук-текст на экране, резкая смена кадра",
        "Боль аудитории одним кадром",
        f"{video.visual_style}: демонстрация приёма",
        "Продукт в деле, без крика",
        "CTA, тот же свет и персонаж",
    ]
    voices = [
        hook,
        "Большинство сливает охваты на старте.",
        f"{product} делает это иначе.",
        f"Короткий приём, который закрывает боль — {product}.",
        cta_voice,
    ]
    storyboard = align_storyboard(
        [
            {"visual": visuals[min(index, len(visuals) - 1)], "voiceover": voices[min(index, len(voices) - 1)]}
            for index in range(len(durations))
        ],
        durations,
    )
    tags = ["контент", "продвижение", (settings.niche or "saas").replace(" ", ""), "reels", "shorts"]
    return {
        "idea": idea,
        "hook": hook,
        "script": script,
        "caption": f"{hook} {(settings.cta_text or '').strip()}".strip(),
        "hashtags": tags,
        "storyboard": storyboard,
        "content_format": video.content_format,
        "visual_style": video.visual_style,
    }


async def _llm_json(
    settings: CustomContentFactorySettings,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    openai_key = decrypted_secret(settings, "openai_api_key")
    try:
        if openai_key:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=openai_key)
            provider = "openai"
        else:
            from ...services.ai_authoring import ai_client as client

            provider = "deepseek"
        response = await client.chat.completions.create(
            model=model or "deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
        )
    except Exception as exc:
        logger.info("Content factory LLM fallback: %s", exc)
        return None
    text = (response.choices[0].message.content or "").strip()
    match = _JSON_BLOCK.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    usage = getattr(response, "usage", None)
    return data, {
        "provider": provider,
        "model": model,
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def _ensure_clip_plan(video: CustomContentFactoryVideo) -> list[dict[str, Any]]:
    extra = dict(video.extra or {})
    plan = extra.get("clip_plan")
    if isinstance(plan, list) and plan:
        return [item if isinstance(item, dict) else {} for item in plan]
    durations = extra.get("clip_durations") or plan_clip_durations(int(video.duration_seconds or 30))
    scenes = list(video.storyboard or [])
    if len(scenes) != len(durations):
        scenes = align_storyboard(scenes, durations)
        video.storyboard = scenes
    plan = []
    for index, duration in enumerate(durations):
        scene = scenes[index] if index < len(scenes) else {}
        plan.append(
            {
                "index": index,
                "duration": int(duration),
                "visual": str(scene.get("visual") or ""),
                "voiceover": str(scene.get("voiceover") or ""),
                "status": "pending",
                "task_id": None,
                "url": None,
                "path": None,
            }
        )
    extra["clip_plan"] = plan
    extra["clips_total"] = len(plan)
    extra["clips_done"] = 0
    extra["kling_cap_seconds"] = 8
    extra["note"] = (
        f"Kling отдаёт до 8с. Собираем {len(plan)} клипов ({sum(int(item['duration']) for item in plan)}с) и склеиваем."
    )
    video.extra = extra
    return plan


async def _stitch_clips(video: CustomContentFactoryVideo) -> None:
    extra = dict(video.extra or {})
    plan = [item if isinstance(item, dict) else {} for item in (extra.get("clip_plan") or [])]
    folder = video_dir(video.custom_automation_id, video.id)
    paths = []
    for index, clip in enumerate(plan):
        local = folder / f"clip-{index:02d}.mp4"
        if local.exists() and local.stat().st_size > 0:
            paths.append(local)
            continue
        url = str(clip.get("url") or "").strip()
        if not url:
            raise RuntimeError(f"Нет файла клипа {index + 1}")
        await download_to_file(url, local)
        clip["path"] = str(local)
        paths.append(local)
    master = folder / "master.mp4"
    extra["render_stage"] = "stitch"
    video.extra = extra
    concat_clips(paths, master)
    thumb = write_thumbnail(master, folder / "thumb.jpg")
    extra["preview"] = False
    extra["stitched"] = True
    extra["awaiting_kling"] = False
    extra["render_stage"] = "done"
    extra["master_path"] = str(master)
    extra["clips"] = [str(clip.get("url") or "") for clip in plan]
    extra["clips_done"] = len(plan)
    extra["note"] = f"Склеено {len(paths)} клипов Kling в {sum(int(item.get('duration') or 0) for item in plan)}с."
    video.extra = extra
    video.video_url = public_media_url(master)
    if thumb:
        video.thumbnail_url = public_media_url(thumb)
    video.render_task_id = None


def _is_grok_carousel(video: CustomContentFactoryVideo, settings: CustomContentFactorySettings) -> bool:
    if str((video.extra or {}).get("media_kind") or "") != "carousel":
        return False
    provider, _model, key = _carousel_key(settings)
    return provider == "grok" and bool(key)


def _apply_grok_copy(video: CustomContentFactoryVideo, settings: CustomContentFactorySettings, pack: dict[str, Any]) -> None:
    text = str(pack.get("text") or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    theme = lines[0] if lines else (settings.product_name or "Карусель")
    video.idea = theme[:2000]
    video.caption = (text or theme)[:2000]
    video.script = video.caption
    video.hook = theme[:300]
    prompts = [str(item).strip() for item in (pack.get("prompts") or []) if str(item).strip()]
    board: list[dict[str, str]] = []
    for index, prompt in enumerate(prompts):
        voice = lines[index] if index < len(lines) else ""
        board.append({"visual": prompt[:500], "voiceover": voice[:400]})
    if board and not any(item["voiceover"] for item in board):
        board[0]["voiceover"] = video.hook
    if board:
        video.storyboard = board


def _carousel_key(settings: CustomContentFactorySettings) -> tuple[str, str, str]:
    provider = str(getattr(settings, "image_provider", "") or "chatgpt").strip().lower()
    if provider not in {"chatgpt", "grok"}:
        provider = "chatgpt"
    model = str(getattr(settings, "image_model", "") or "").strip()
    if provider == "grok":
        return provider, model or "grok-imagine-image-2.0", _xai_key(settings)
    key = decrypted_secret(settings, "openai_api_key") or (app_settings.OPENAI_API_KEY or "").strip()
    return provider, model or "gpt-image-2.5-flare", key


async def _render_carousel(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    provider, model, api_key = _carousel_key(settings)
    if not api_key:
        raise RuntimeError("Для фото-карусели нужен API-ключ ChatGPT или Grok")
    slides = [item for item in (video.storyboard or []) if isinstance(item, dict)][:6]
    if len(slides) < 2:
        slides = [
            {"visual": f"Vertical editorial photo about {settings.product_name or 'the product'}, frame {index + 1}, no text", "voiceover": ""}
            for index in range(5)
        ]
    folder = video_dir(video.custom_automation_id, video.id)
    paths: list[Path] = []
    urls: list[str] = []
    bot_id = ""
    if provider == "grok":
        used = await recent_hooks(session, video.custom_automation_id)
        bot_id = factory_grok_bot_id(video.custom_automation_id)
        pack = await generate_grok_carousel_pack(
            api_key=api_key,
            company=settings.product_name or "",
            description=settings.product_description or "",
            audience=settings.audience or "",
            niche=settings.niche or "",
            brief=str(getattr(settings, "grok_bot_brief", "") or ""),
            avoid=used,
            previous_response_id=str(getattr(settings, "grok_bot_response_id", "") or ""),
            folder=folder,
        )
        paths = list(pack["paths"])
        urls = [public_media_url(path) for path in paths]
        _apply_grok_copy(video, settings, pack)
        video.started_at = video.started_at or now_utc()
        if pack.get("response_id"):
            settings.grok_bot_response_id = str(pack["response_id"])[:2000]
            settings.updated_at = now_utc()
    else:
        for index, slide in enumerate(slides):
            prompt = str(slide.get("visual") or slide.get("voiceover") or settings.product_name or "editorial photo")
            dest = folder / f"slide-{index:02d}.png"
            await generate_slide_png(provider=provider, model=model, api_key=api_key, prompt=prompt, dest=dest)
            paths.append(dest)
            urls.append(public_media_url(dest))
    extra = dict(video.extra or {})
    extra["media_kind"] = "carousel"
    extra["slide_urls"] = urls
    extra["slides_done"] = len(urls)
    if bot_id:
        extra["grok_bot_id"] = bot_id
    extra["note"] = (
        f"Карусель из {len(urls)} кадров"
        + (f", бот {bot_id}" if bot_id else f" ({provider})")
        + ". Instagram, TikTok и Pinterest публикуют кадры в этом порядке. YouTube и VK Клипы получают слайд-шоу."
    )
    extra["awaiting_kling"] = False
    show = folder / "slideshow.mp4"
    try:
        slides_to_mp4(paths, show, seconds=2.4)
        video.video_url = public_media_url(show)
        thumb = write_thumbnail(show, folder / "thumb.jpg")
        if thumb:
            video.thumbnail_url = public_media_url(thumb)
    except Exception as exc:
        extra["slideshow_error"] = str(exc)[:300]
        video.video_url = None
    video.extra = extra
    video.status = "uniqualizing"
    await record_token_usage(
        session,
        automation_id=video.custom_automation_id,
        video_id=video.id,
        provider=provider,
        model=model,
        operation="carousel",
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=0.04 * len(paths),
    )


async def _render_video(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    kling_key = decrypted_secret(settings, "kling_api_key") or (app_settings.KLING_API_KEY or "").strip()
    model = (settings.video_model or "kling").strip().lower()
    extra = dict(video.extra or {})
    if model in {"runway", "luma"}:
        extra["preview"] = True
        extra["awaiting_kling"] = False
        extra["note"] = "Runway и Luma пока не подключены. Выберите Kling или раскадровку."
        video.extra = extra
        video.video_url = None
        video.status = "uniqualizing"
        return
    if model == "kling" and kling_key:
        client = KlingClient(api_key=kling_key)
        plan = _ensure_clip_plan(video)
        extra = dict(video.extra or {})
        current = next((item for item in plan if not item.get("url")), None)
        if current is None:
            await _stitch_clips(video)
            video.status = "uniqualizing"
            return
        index = int(current.get("index") or 0)
        extra["render_stage"] = "clip"
        extra["clips_done"] = sum(1 for item in plan if item.get("url"))
        extra["note"] = f"Генерация клипа {index + 1}/{len(plan)} ({current.get('duration')}с)."
        if not current.get("task_id"):
            prompt = clip_prompt(
                settings_row=settings,
                video=video,
                clip=current,
                index=index,
                total=len(plan),
            )
            duration = max(5, min(8, int(current.get("duration") or 8)))
            task_id = await client.submit_render(
                script_text=prompt,
                duration_seconds=duration,
                model="kling-v1",
                idempotency_key=f"cf-{video.id}-c{index}",
            )
            current["task_id"] = task_id
            current["status"] = "rendering"
            extra["clip_plan"] = plan
            extra["awaiting_kling"] = True
            video.render_task_id = task_id
            video.extra = extra
            await record_token_usage(
                session,
                automation_id=video.custom_automation_id,
                video_id=video.id,
                provider="kling",
                model="kling-v1",
                operation="render",
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=estimate_render_cost_usd(video_model="kling", duration_seconds=duration),
            )
            return
        polls = int(extra.get("kling_polls") or 0) + 1
        extra["kling_polls"] = polls
        video.extra = extra
        if polls > KLING_POLL_LIMIT:
            extra["awaiting_kling"] = False
            video.extra = extra
            raise RuntimeError(f"Kling не завершил клип {index + 1} за {KLING_POLL_LIMIT} проверок")
        payload = await client.poll_render(task_id=str(current["task_id"]))
        status = str(payload.get("status") or "")
        if status == "rendered":
            url = str(payload.get("video_url") or "").strip()
            if not url:
                raise RuntimeError(f"Kling не вернул URL клипа {index + 1}")
            folder = video_dir(video.custom_automation_id, video.id)
            local = folder / f"clip-{index:02d}.mp4"
            try:
                await download_to_file(url, local)
                current["path"] = str(local)
            except Exception as exc:
                logger.info("Clip download deferred: %s", exc)
            current["url"] = url
            current["status"] = "rendered"
            extra["kling_polls"] = 0
            extra["clip_plan"] = plan
            extra["clips"] = [str(item.get("url") or "") for item in plan if item.get("url")]
            extra["clips_done"] = sum(1 for item in plan if item.get("url"))
            extra["awaiting_kling"] = False
            video.render_task_id = None
            video.extra = extra
            if extra["clips_done"] >= len(plan):
                await _stitch_clips(video)
                video.status = "uniqualizing"
            return
        if status == "failed":
            current["status"] = "failed"
            extra["clip_plan"] = plan
            extra["awaiting_kling"] = False
            video.extra = extra
            raise RuntimeError(payload.get("error") or f"kling_failed clip {index + 1}")
        extra["clip_plan"] = plan
        extra["awaiting_kling"] = True
        video.render_task_id = str(current.get("task_id") or "")
        video.extra = extra
        return
    extra["preview"] = True
    extra["awaiting_kling"] = False
    extra["note"] = "Ролик собран как раскадровка: подключите Kling, чтобы получить файл."
    video.extra = extra
    video.video_url = None
    video.status = "uniqualizing"
    await record_token_usage(
        session,
        automation_id=video.custom_automation_id,
        video_id=video.id,
        provider=settings.video_model or "preview",
        model=settings.video_model or "preview",
        operation="render",
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=0.0,
    )


_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"


async def _attach_soundtrack(
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    mode = str(getattr(settings, "music_mode", "") or "voice_bed").strip().lower()
    if mode not in {"bed", "voice", "voice_bed"}:
        return
    extra = dict(video.extra or {})
    if extra.get("soundtrack_applied"):
        return
    master = local_path_from_url(video.video_url)
    if not master or not master.exists() or master.stat().st_size <= 0:
        return
    folder = video_dir(video.custom_automation_id, video.id)
    want_voice = mode in {"voice", "voice_bed"}
    want_bed = mode in {"bed", "voice_bed"}
    bed_path = None
    voice_path = None
    note = ""
    if want_bed or mode == "voice":
        bed_path = write_music_bed(folder / "bed.wav", seed=f"{video.id}:{video.hook}")
    if want_voice:
        speech = voiceover_lines(video)
        api_key = decrypted_secret(settings, "elevenlabs_api_key")
        voice_id = str(getattr(settings, "tts_voice", "") or "").strip() or _DEFAULT_VOICE
        model_id = str(settings.tts_model or "").strip() or "eleven_multilingual_v2"
        if api_key and speech:
            try:
                voice_path = await synthesize_voiceover(
                    api_key=api_key,
                    voice_id=voice_id,
                    model_id=model_id,
                    text=speech,
                    dest=folder / "voice.mp3",
                )
            except Exception as exc:
                note = f"Озвучка не собралась: {exc}"[:240]
                logger.warning("Content factory voiceover skipped for %s: %s", video.id, exc)
        else:
            note = "Озвучки нет: нужен ключ ElevenLabs. На слайд-шоу остаётся своя подложка."
    if mode == "voice" and voice_path is None and bed_path is None:
        extra["soundtrack_error"] = note or "Нет дорожки"
        video.extra = extra
        return
    if mode == "voice" and voice_path is not None:
        bed_path = None
    dest = folder / "with-audio.mp4"
    volume = max(0, min(100, int(getattr(settings, "music_volume", 32) or 32))) / 100.0
    try:
        mix_soundtrack(
            video=master,
            dest=dest,
            bed=bed_path,
            voice=voice_path,
            bed_volume=volume,
        )
    except Exception as exc:
        extra["soundtrack_error"] = str(exc)[:240]
        video.extra = extra
        return
    video.video_url = public_media_url(dest)
    extra["soundtrack_applied"] = True
    extra["soundtrack"] = {
        "mode": "voice_bed" if voice_path and bed_path else ("voice" if voice_path else "bed"),
        "voice": bool(voice_path),
        "bed": bool(bed_path),
    }
    if note and not voice_path:
        extra["soundtrack_note"] = note
    video.extra = extra


async def _uniqualize(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    await _attach_soundtrack(video, settings)
    accounts = list(
        (
            await session.execute(
                select(CustomContentFactoryAccount).where(
                    CustomContentFactoryAccount.custom_automation_id == video.custom_automation_id,
                    CustomContentFactoryAccount.is_enabled.is_(True),
                )
            )
        ).scalars().all()
    )
    recipes = recipes_for_video(video, settings, accounts)
    digest = uniqueness_hash(script=video.script, hook=video.hook, recipes=recipes)
    collision = await session.scalar(
        select(CustomContentFactoryVideo.id).where(
            CustomContentFactoryVideo.custom_automation_id == video.custom_automation_id,
            CustomContentFactoryVideo.uniqueness_hash == digest,
            CustomContentFactoryVideo.id != video.id,
        )
    )
    if collision:
        salted = recipes_for_video(video, settings, accounts)
        for payload in salted.values():
            if isinstance(payload, dict):
                payload["salt"] = f"v{video.id}"
        recipes = salted
        digest = uniqueness_hash(script=video.script, hook=video.hook, recipes=recipes)
    master = local_path_from_url(video.video_url)
    if master and master.exists() and master.stat().st_size > 0:
        folder = video_dir(video.custom_automation_id, video.id)
        encoded: dict[str, tuple[str, str]] = {}
        for key, recipe in recipes.items():
            if not isinstance(recipe, dict):
                continue
            platform = str(recipe.get("platform") or str(key).split(":", 1)[0] or "youtube")
            shared = encoded.get(platform)
            if shared:
                recipe["video_url"], recipe["path"] = shared
                continue
            dest = folder / f"uniq-{platform}.mp4"
            uniqualize_file(
                source=master,
                dest=dest,
                recipe=recipe,
                aspect_ratio=video.aspect_ratio or "9:16",
            )
            url = public_media_url(dest)
            recipe["video_url"] = url
            recipe["path"] = str(dest)
            encoded[platform] = (url, str(dest))
    elif video.video_url:
        for recipe in recipes.values():
            if isinstance(recipe, dict) and not recipe.get("video_url"):
                recipe["video_url"] = video.video_url
    video.uniqualization = recipes
    video.uniqueness_hash = digest
    video.status = "ready"
    video.last_error = None


def _mark_publish_failure(post: CustomContentFactoryPost, account: CustomContentFactoryAccount, message: str) -> None:
    meta = dict(post.uniqualization_applied or {})
    attempts = int(meta.get("attempts") or 0) + 1
    meta["attempts"] = attempts
    delay_min = min(180, 2 ** min(attempts, 7))
    meta["retry_after"] = (now_utc() + timedelta(minutes=delay_min)).isoformat()
    post.uniqualization_applied = meta
    post.status = "failed"
    post.hold_reason = message[:500]
    account.last_error = message[:500]


def _failure_keeps_video(post: CustomContentFactoryPost) -> bool:
    if post.status != "failed":
        return False
    return int((post.uniqualization_applied or {}).get("attempts") or 0) < PUBLISH_ATTEMPT_LIMIT


async def _post_video(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    existing_rows = list(
        (
            await session.execute(
                select(CustomContentFactoryPost).where(CustomContentFactoryPost.video_id == video.id)
            )
        ).scalars().all()
    )
    existing = {post.account_id: post for post in existing_rows}
    accounts = list(
        (
            await session.execute(
                select(CustomContentFactoryAccount).where(
                    CustomContentFactoryAccount.custom_automation_id == video.custom_automation_id,
                    CustomContentFactoryAccount.is_enabled.is_(True),
                )
            )
        ).scalars().all()
    )
    extra = dict(video.extra or {})
    manual = bool(extra.get("manual"))
    manual_account_id = int(extra.get("manual_account_id") or 0) if manual else 0
    if manual_account_id:
        accounts = [item for item in accounts if int(item.id) == manual_account_id]
    if not accounts:
        video.status = "ready"
        extra["hold_reason"] = "Нет подключённых аккаунтов"
        video.extra = extra
        video.last_error = None
        return
    needs_poll = any(post.status == "processing" for post in existing_rows)
    if not settings.sandbox_mode and not needs_poll and not manual:
        if not in_posting_window(
            timezone_name=settings.timezone,
            start=settings.posting_window_start,
            end=settings.posting_window_end,
        ):
            video.status = "ready"
            extra["hold_reason"] = "Вне окна публикаций"
            video.extra = extra
            return
        if video.scheduled_for and video.scheduled_for > now_utc():
            video.status = "ready"
            video.extra = extra
            return
    video.status = "posting"
    stagger_until = parse_utc_naive(str(extra.get("next_publish_at") or ""))
    stagger_open = bool(settings.sandbox_mode) or stagger_until is None or now_utc() >= stagger_until
    attempted_this_tick = 0
    for account in accounts:
        reset_daily_counter(account, timezone_name=settings.timezone or "Europe/Moscow")
        progress = warmup_progress(
            started_at=account.warmup_started_at,
            completed_at=account.warmup_completed_at,
            actions_done=int(account.warmup_actions_done or 0),
            warmup_days=int(settings.warmup_days or 7),
            actions_per_day=int(settings.warmup_actions_per_day or 8),
        )
        daily_cap = live_daily_cap(
            max_posts_per_day=int(settings.max_posts_per_account_per_day or 2),
            warmup_completed_at=account.warmup_completed_at,
            owner_confirmed=bool((account.extra or {}).get("owner_confirmed")),
            ramp=False if manual else bool((account.extra or {}).get("apply_post_ramp")),
        )
        if settings.sandbox_mode:
            allowed, reason = True, ""
        else:
            allowed, reason = can_post_from_account(
                status=account.status,
                is_enabled=account.is_enabled,
                warmup=progress,
                posts_today=int(account.posts_today or 0),
                max_posts_per_day=daily_cap,
                last_posted_at=account.last_posted_at,
                stagger_min_minutes=int(settings.stagger_min_minutes or 25),
            )
        post = existing.get(account.id)
        if post is None:
            post = CustomContentFactoryPost(
                video_id=video.id,
                account_id=account.id,
                platform=account.platform,
                status="pending",
                created_at=now_utc(),
            )
            session.add(post)
            await session.flush()
            existing[account.id] = post
        if post.status in {"posted", "sandbox"}:
            continue
        if post.status == "processing":
            started = parse_utc_naive(str((post.uniqualization_applied or {}).get("processing_since") or ""))
            if started and now_utc() - started > PROCESSING_TIMEOUT:
                _mark_publish_failure(post, account, "Площадка не подтвердила публикацию за 6 часов")
                attempted_this_tick += 1
                continue
        if post.status == "failed":
            meta = post.uniqualization_applied or {}
            due = publish_attempt_due(
                attempts=int(meta.get("attempts") or 0),
                retry_after=parse_utc_naive(str(meta.get("retry_after") or "")),
            )
            if not due:
                continue
        if not allowed and post.status != "processing":
            post.status = "held"
            post.hold_reason = reason
            continue
        if not stagger_open and post.status != "processing":
            if post.status not in {"held", "failed"}:
                post.status = "pending"
                post.hold_reason = "Пауза между аккаунтами"
            continue
        if not settings.sandbox_mode and attempted_this_tick >= 1 and post.status != "processing":
            if post.status not in {"held", "failed"}:
                post.status = "pending"
                post.hold_reason = "Пауза между аккаунтами"
            continue
        recipe_map = video.uniqualization or {}
        recipe = dict(recipe_map.get(f"{account.platform}:{account.id}") or recipe_map.get(account.platform) or {})
        publisher_state = {
            key: value
            for key, value in (post.uniqualization_applied or {}).items()
            if key.startswith(("ig_", "tiktok_", "vk_"))
        }
        variant = caption_variant(
            video.caption,
            account.platform,
            settings.product_url,
            seed=f"{video.id}:{account.id}",
            hashtags=list(video.hashtags or []),
        )
        proxy_url = ""
        if not settings.sandbox_mode:
            proxy_url = await proxy_url_for_account(session, account)
            if not proxy_url:
                if post.status != "processing":
                    post.status = "held"
                    post.hold_reason = PROXY_MISSING
                if not str(account.last_error or "").strip():
                    account.last_error = PROXY_MISSING
                continue
        try:
            result = await publish_to_platform(
                platform=account.platform,
                credentials=decrypt_json(account.credentials_enc),
                video_url=str(recipe.get("video_url") or video.video_url or ""),
                title=(video.hook or video.idea or settings.product_name or "Ролик")[:100],
                caption=variant,
                sandbox=bool(settings.sandbox_mode),
                video_id=video.id,
                account_id=account.id,
                publisher_state=publisher_state,
                image_urls=list((video.extra or {}).get("slide_urls") or [])
                if str((video.extra or {}).get("media_kind") or "") == "carousel"
                else None,
                proxy_url=proxy_url or None,
            )
        except PublisherError as exc:
            _mark_publish_failure(post, account, str(exc))
            attempted_this_tick += 1
            continue
        except Exception as exc:
            logger.exception("Content factory publish failed video=%s account=%s", video.id, account.id)
            _mark_publish_failure(post, account, str(exc))
            attempted_this_tick += 1
            continue
        status = str(result.get("status") or "posted")
        post.status = status
        post.external_id = str(result.get("external_id") or "")
        post.posted_url = str(result.get("posted_url") or "")
        post.caption_variant = variant
        applied = dict(recipe)
        if isinstance(result.get("publisher_state"), dict):
            applied.update(result["publisher_state"])
        if status == "processing" and not applied.get("processing_since"):
            applied["processing_since"] = now_utc().isoformat()
        post.uniqualization_applied = applied
        post.hold_reason = str(result.get("note") or "") or None
        if status == "posted" and not settings.sandbox_mode:
            post.posted_at = now_utc()
            account.last_posted_at = now_utc()
            account.posts_today = int(account.posts_today or 0) + 1
            account.last_error = None
            if account.status in {"connected", "ready", "warming"}:
                account.status = "ready"
            wait = timedelta(minutes=max(5, int(settings.stagger_min_minutes or 25)))
            stagger_until = now_utc() + wait
            extra["next_publish_at"] = stagger_until.isoformat()
            video.extra = extra
            stagger_open = False
        elif status == "sandbox":
            post.posted_at = now_utc()
            account.last_error = None
        attempted_this_tick += 1
        bundle = result.get("token_bundle")
        if isinstance(bundle, dict) and bundle:
            account.credentials_enc = encrypt_json(
                merge_platform_credentials(decrypt_json(account.credentials_enc), bundle)
            )
        if not settings.sandbox_mode and post.external_id:
            await session.commit()
    statuses = [item.status for item in existing.values()]
    has_retryable = any(_failure_keeps_video(item) for item in existing.values())
    video.status = settle_publish_status(statuses, has_retryable_failure=has_retryable)
    if video.status in {"posted", "sandbox"}:
        video.finished_at = now_utc()
        failed = [item.hold_reason for item in existing.values() if item.status == "failed" and item.hold_reason]
        video.last_error = failed[0][:800] if failed else None
        if failed:
            extra["hold_reason"] = "Часть площадок опубликована, остальные исчерпали попытки"
        else:
            extra.pop("hold_reason", None)
    elif video.status == "failed":
        video.finished_at = now_utc()
        video.last_error = next((item.hold_reason for item in existing.values() if item.hold_reason), "Не удалось опубликовать")
        extra["hold_reason"] = video.last_error
    elif video.status == "posting":
        video.last_error = None
        extra["hold_reason"] = "Публикация продолжается по аккаунтам с паузой"
    else:
        video.last_error = None
        extra["hold_reason"] = next(
            (item.hold_reason for item in existing.values() if item.status in {"held", "pending", "failed"} and item.hold_reason),
            "Постинг отложен",
        )
        if not statuses:
            extra["hold_reason"] = "Нет площадок для публикации"
    video.extra = extra


_OWN_IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
_OWN_VIDEO = {".mp4", ".mov", ".webm"}


async def publish_own_material(
    session: AsyncSession,
    *,
    automation_id: int,
    account_id: int,
    title: str,
    caption: str,
    media_kind: str,
    files: list[tuple[str, bytes]],
) -> CustomContentFactoryVideo:
    """Publish the owner's file through the same poster. Do not regenerate it."""
    from pathlib import Path

    kind = str(media_kind or "").strip().lower()
    if kind not in {"carousel", "video"}:
        raise ValueError("Нужно видео или фото-карусель")
    if kind == "video" and len(files) != 1:
        raise ValueError("Для ролика нужен один файл")
    if kind == "carousel" and not (2 <= len(files) <= 10):
        raise ValueError("Для карусели нужно от 2 до 10 фото в порядке публикации")
    account = await session.get(CustomContentFactoryAccount, int(account_id))
    if account is None or int(account.custom_automation_id) != int(automation_id) or not account.is_enabled:
        raise ValueError("Аккаунт завода не найден")
    text = str(caption or "").strip()
    headline = str(title or "").strip() or text[:100] or "Свой материал"
    if not text and not headline:
        raise ValueError("Нужно описание")
    now = now_utc()
    video = CustomContentFactoryVideo(
        custom_automation_id=automation_id,
        status="ready",
        scheduled_for=now,
        started_at=now,
        idea=headline[:2000],
        hook=headline[:300],
        script=(text or headline)[:8000],
        caption=(text or headline)[:2000],
        hashtags=[],
        content_format="ugc",
        visual_style="realism",
        duration_seconds=15,
        aspect_ratio="9:16",
        storyboard=[],
        uniqualization={},
        uniqueness_hash=hashlib.sha256(f"manual:{account_id}:{now.isoformat()}:{headline}".encode()).hexdigest(),
        extra={
            "manual": True,
            "manual_account_id": int(account.id),
            "media_kind": kind,
            "source": "manual",
        },
        created_at=now,
        updated_at=now,
    )
    session.add(video)
    await session.flush()
    folder = video_dir(automation_id, video.id)
    urls: list[str] = []
    names: list[str] = []
    for index, (name, blob) in enumerate(files):
        if not blob:
            raise ValueError("Пустой файл")
        suffix = Path(str(name or "")).suffix.lower()
        allowed = _OWN_IMAGE if kind == "carousel" else _OWN_VIDEO
        if suffix not in allowed:
            raise ValueError("Формат файла эта площадка в таком виде не примет")
        filename = f"slide-{index:02d}{suffix}" if kind == "carousel" else f"own{suffix}"
        dest = folder / filename
        dest.write_bytes(blob)
        urls.append(public_media_url(dest))
        names.append(filename)
    extra = dict(video.extra or {})
    extra["slide_names"] = names
    if kind == "carousel":
        extra["slide_urls"] = urls
        extra["slides_done"] = len(urls)
        video.storyboard = [{"visual": name, "voiceover": ""} for name in names]
        show = folder / "slideshow.mp4"
        try:
            slides_to_mp4([folder / name for name in names], show, seconds=2.4)
            video.video_url = public_media_url(show)
        except Exception as exc:
            extra["slideshow_error"] = str(exc)[:300]
            video.video_url = None
    else:
        video.video_url = urls[0]
    extra["note"] = "Свой материал. Завод его не перегенерирует."
    video.extra = extra
    settings = await get_or_create_settings(session, automation_id)
    await _post_video(session, video, settings)
    await session.flush()
    return video


def _finish_warmup(account: CustomContentFactoryAccount) -> None:
    """Close the calendar gate. Ramp applies only to accounts that finish after this release."""
    account.warmup_completed_at = account.warmup_completed_at or now_utc()
    if account.status != "warming":
        return
    account.status = "ready"
    if (account.extra or {}).get("owner_confirmed"):
        return
    extra = dict(account.extra or {})
    extra["apply_post_ramp"] = True
    account.extra = extra


async def _advance_warmup(
    session: AsyncSession,
    automation_id: int,
    settings: CustomContentFactorySettings,
) -> int:
    accounts = list(
        (
            await session.execute(
                select(CustomContentFactoryAccount).where(
                    CustomContentFactoryAccount.custom_automation_id == automation_id,
                    CustomContentFactoryAccount.is_enabled.is_(True),
                )
            )
        ).scalars().all()
    )
    created = 0
    for account in accounts:
        if account.status in {"paused", "restricted", "disconnected"}:
            continue
        if not account.warmup_started_at:
            account.warmup_started_at = now_utc()
            account.status = "warming"
        progress = warmup_progress(
            started_at=account.warmup_started_at,
            completed_at=account.warmup_completed_at,
            actions_done=int(account.warmup_actions_done or 0),
            warmup_days=int(settings.warmup_days or 7),
            actions_per_day=int(settings.warmup_actions_per_day or 8),
        )
        if progress["complete"]:
            _finish_warmup(account)
            continue
        if account.status != "warming":
            account.status = "warming"
        last_event_at = await session.scalar(
            select(func.max(CustomContentFactoryWarmupEvent.created_at)).where(
                CustomContentFactoryWarmupEvent.account_id == account.id
            )
        )
        interval = warmup_action_interval(int(settings.warmup_actions_per_day or 8))
        if last_event_at and now_utc() < last_event_at + interval:
            continue
        day_start = local_midnight_utc_naive(settings.timezone or "Europe/Moscow")
        today_count = int(
            await session.scalar(
                select(func.count()).select_from(CustomContentFactoryWarmupEvent).where(
                    CustomContentFactoryWarmupEvent.account_id == account.id,
                    CustomContentFactoryWarmupEvent.created_at >= day_start,
                )
            )
            or 0
        )
        if today_count >= max(2, min(int(settings.warmup_actions_per_day or 8), 20)):
            continue
        seed = f"{account.id}:{now_utc().date()}:{account.warmup_actions_done}"
        action, detail = pick_warmup_action(seed)
        await add_warmup_event(session, account, action_type=action, detail=detail)
        created += 1
        progress = warmup_progress(
            started_at=account.warmup_started_at,
            completed_at=account.warmup_completed_at,
            actions_done=int(account.warmup_actions_done or 0),
            warmup_days=int(settings.warmup_days or 7),
            actions_per_day=int(settings.warmup_actions_per_day or 8),
        )
        if progress["complete"]:
            _finish_warmup(account)
    return created


async def _apply_shadowban_guards(
    session: AsyncSession,
    automation_id: int,
    settings: CustomContentFactorySettings,
) -> int:
    if not settings.shadowban_pause_zero_views:
        return 0
    accounts = list(
        (
            await session.execute(
                select(CustomContentFactoryAccount).where(
                    CustomContentFactoryAccount.custom_automation_id == automation_id
                )
            )
        ).scalars().all()
    )
    flagged = 0
    for account in accounts:
        posts = list(
            (
                await session.execute(
                    select(CustomContentFactoryPost)
                    .where(CustomContentFactoryPost.account_id == account.id)
                    .order_by(CustomContentFactoryPost.posted_at.desc())
                    .limit(8)
                )
            ).scalars().all()
        )
        payload = [
            {
                "status": item.status,
                "posted_at": item.posted_at,
                "views": item.views,
                "views_known": bool(item.analytics_synced_at) and not (item.uniqualization_applied or {}).get("views_unreliable"),
            }
            for item in posts
        ]
        recent_views = sum(int(item.views or 0) for item in posts[:3])
        if account.status == "shadow_risk" and should_clear_shadowban(recent_posts=payload):
            account.status = "ready"
            account.risk_flags = [flag for flag in (account.risk_flags or []) if flag != "shadowban"]
            extra = dict(account.extra or {})
            extra["shadowban_recovered_at"] = now_utc().isoformat()
            account.extra = extra
            account.last_error = None
        elif should_flag_shadowban(
            recent_posts=payload,
            threshold=int(settings.shadowban_zero_views_threshold or 3),
        ):
            if "shadowban" not in (account.risk_flags or []):
                flags = list(account.risk_flags or [])
                flags.append("shadowban")
                account.risk_flags = flags
            if account.status not in {"restricted", "paused"}:
                account.status = "shadow_risk"
            flagged += 1
        progress = warmup_progress(
            started_at=account.warmup_started_at,
            completed_at=account.warmup_completed_at,
            actions_done=int(account.warmup_actions_done or 0),
            warmup_days=int(settings.warmup_days or 7),
            actions_per_day=int(settings.warmup_actions_per_day or 8),
        )
        account.health_score = compute_health_score(
            status=account.status,
            warmup_complete=bool(progress.get("complete")),
            last_error=account.last_error,
            risk_flags=list(account.risk_flags or []),
            recent_views=recent_views,
        )
    return flagged


async def _sync_analytics(session: AsyncSession, automation_id: int) -> int:
    result = await session.execute(
        select(CustomContentFactoryPost)
        .join(CustomContentFactoryVideo)
        .options(selectinload(CustomContentFactoryPost.account))
        .where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryPost.status == "posted",
            CustomContentFactoryPost.external_id != "",
        )
        .order_by(
            CustomContentFactoryPost.analytics_synced_at.is_(None).desc(),
            CustomContentFactoryPost.posted_at.asc(),
        )
        .limit(12)
    )
    updated = 0
    for post in result.scalars().all():
        account = post.account
        if not account:
            continue
        proxy_url = await proxy_url_for_account(session, account)
        if not proxy_url:
            continue
        stats = await fetch_post_analytics(
            platform=post.platform,
            credentials=decrypt_json(account.credentials_enc),
            external_id=post.external_id,
            proxy_url=proxy_url,
        )
        if not stats:
            continue
        bundle = stats.get("token_bundle") if isinstance(stats.get("token_bundle"), dict) else None
        unreliable = bool(stats.get("views_unreliable"))
        if not unreliable:
            post.views = int(stats.get("views") or 0)
        post.likes = int(stats.get("likes") or 0)
        post.comments = int(stats.get("comments") or 0)
        post.shares = int(stats.get("shares") or 0)
        post.saves = int(stats.get("saves") or 0)
        applied = dict(post.uniqualization_applied or {})
        applied["views_unreliable"] = unreliable
        post.uniqualization_applied = applied
        if not unreliable:
            post.analytics_synced_at = now_utc()
        if isinstance(bundle, dict) and bundle.get("access_token"):
            account.credentials_enc = encrypt_json(
                merge_platform_credentials(decrypt_json(account.credentials_enc), bundle)
            )
        updated += 1
    return updated
