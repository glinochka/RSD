"""Autonomous idea → render → uniqualize → post loop."""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
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
    now_utc,
    pick_warmup_action,
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
    local_path_from_url,
    plan_clip_durations,
    public_media_url,
    uniqualize_file,
    video_dir,
    write_thumbnail,
)
from .content_factory_publishers import PublisherError, fetch_post_analytics, publish_to_platform
from .content_factory_service import (
    add_warmup_event,
    decrypt_json,
    decrypted_secret,
    get_or_create_settings,
    recent_hooks,
    recipes_for_video,
    record_token_usage,
    reset_daily_counter,
)

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
        extra={},
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(video)
    settings.last_enqueued_at = now_utc()
    settings.updated_at = now_utc()
    await session.flush()
    return video


async def _process_next_video(
    session: AsyncSession,
    automation_id: int,
    settings: CustomContentFactorySettings,
) -> CustomContentFactoryVideo | None:
    result = await session.execute(
        select(CustomContentFactoryVideo)
        .options(selectinload(CustomContentFactoryVideo.posts))
        .where(
            CustomContentFactoryVideo.custom_automation_id == automation_id,
            CustomContentFactoryVideo.status.in_(tuple(VIDEO_IN_FLIGHT)),
        )
        .order_by(CustomContentFactoryVideo.scheduled_for.asc(), CustomContentFactoryVideo.id.asc())
        .limit(1)
    )
    video = result.scalars().first()
    if not video:
        return None
    if video.status in {"ready", "posting"} and video.scheduled_for and video.scheduled_for > now_utc() + timedelta(minutes=2):
        return video
    await _advance_video(session, video, settings)
    return video


async def _advance_video(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    try:
        if video.status == "queued":
            await _write_idea_and_script(session, video, settings)
        elif video.status in {"ideating", "scripting"}:
            await _write_idea_and_script(session, video, settings)
        elif video.status == "rendering":
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
    pack = await _generate_pack(settings, video, used)
    hook = str(pack.get("hook") or "").strip()
    if settings.hook_required and not hook_is_strong(hook):
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


async def _generate_pack(
    settings: CustomContentFactorySettings,
    video: CustomContentFactoryVideo,
    used_hooks: list[str],
) -> dict[str, Any]:
    fallback = _fallback_pack(settings, video, used_hooks)
    prompt = _authoring_prompt(settings, video, used_hooks)
    completion = await _llm_json(
        settings,
        system_prompt="Ты сценарист коротких вертикальных роликов 30-60 секунд. Верни только JSON.",
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


def _authoring_prompt(settings: CustomContentFactorySettings, video: CustomContentFactoryVideo, used_hooks: list[str]) -> str:
    durations = plan_clip_durations(int(video.duration_seconds or 30))
    starts = []
    cursor = 0
    for length in durations:
        starts.append(cursor)
        cursor += length
    return (
        f"Продукт: {settings.product_name or 'сервис'}\n"
        f"Описание: {settings.product_description}\n"
        f"Аудитория: {settings.audience}\n"
        f"Ниша: {settings.niche}\n"
        f"Формат: {video.content_format}; стиль: {video.visual_style}; язык: {settings.language}\n"
        f"Тон: {settings.tone}. Голос бренда: {settings.brand_voice}\n"
        f"Нельзя: {settings.forbidden_topics or 'кликбейт про гарантии дохода, фейковые отзывы'}\n"
        f"Длительность: {sum(durations)}с, кадр {video.aspect_ratio}.\n"
        f"Клипы Kling по 5–8с, будет склейка: {durations}. Старт сцен: {starts}.\n"
        f"Не повторяй хуки: {used_hooks[:8]}\n"
        "Нужен сильный хук в первую секунду (вопрос, стоп-кадр, конкретная цифра).\n"
        f"storyboard — ровно {len(durations)} сцен, каждая под свой клип, единый персонаж и свет.\n"
        "JSON поля: idea, hook, script, caption, hashtags (массив), storyboard "
        "(массив {t, duration, visual, voiceover}), content_format, visual_style."
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


async def _uniqualize(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
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
    platforms = []
    seen = set()
    for account in accounts:
        if account.platform not in seen:
            platforms.append(account.platform)
            seen.add(account.platform)
    if not platforms:
        platforms = ["youtube"]
    recipes = recipes_for_video(video, settings, platforms)
    digest = uniqueness_hash(script=video.script, hook=video.hook, recipes=recipes)
    collision = await session.scalar(
        select(CustomContentFactoryVideo.id).where(
            CustomContentFactoryVideo.custom_automation_id == video.custom_automation_id,
            CustomContentFactoryVideo.uniqueness_hash == digest,
            CustomContentFactoryVideo.id != video.id,
        )
    )
    if collision:
        salted = recipes_for_video(video, settings, platforms)
        for payload in salted.values():
            if isinstance(payload, dict):
                payload["salt"] = f"v{video.id}"
        recipes = salted
        digest = uniqueness_hash(script=video.script, hook=video.hook, recipes=recipes)
    master = local_path_from_url(video.video_url)
    if master and master.exists() and master.stat().st_size > 0:
        folder = video_dir(video.custom_automation_id, video.id)
        for platform, recipe in recipes.items():
            if not isinstance(recipe, dict):
                continue
            dest = folder / f"uniq-{platform}.mp4"
            uniqualize_file(
                source=master,
                dest=dest,
                recipe=recipe,
                aspect_ratio=video.aspect_ratio or "9:16",
            )
            recipe["video_url"] = public_media_url(dest)
            recipe["path"] = str(dest)
    elif video.video_url:
        for recipe in recipes.values():
            if isinstance(recipe, dict) and not recipe.get("video_url"):
                recipe["video_url"] = video.video_url
    video.uniqualization = recipes
    video.uniqueness_hash = digest
    video.status = "ready"
    video.last_error = None


async def _post_video(
    session: AsyncSession,
    video: CustomContentFactoryVideo,
    settings: CustomContentFactorySettings,
) -> None:
    if not in_posting_window(
        timezone_name=settings.timezone,
        start=settings.posting_window_start,
        end=settings.posting_window_end,
    ) and not settings.sandbox_mode:
        video.status = "ready"
        extra = dict(video.extra or {})
        extra["hold_reason"] = "Вне окна публикаций"
        video.extra = extra
        return
    if video.scheduled_for and video.scheduled_for > now_utc() and not settings.sandbox_mode:
        video.status = "ready"
        return
    video.status = "posting"
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
    if not accounts:
        video.status = "ready"
        extra["hold_reason"] = "Нет подключённых аккаунтов"
        video.extra = extra
        video.last_error = None
        return
    stagger = not bool(settings.sandbox_mode)
    published_this_tick = 0
    for account in accounts:
        reset_daily_counter(account)
        progress = warmup_progress(
            started_at=account.warmup_started_at,
            completed_at=account.warmup_completed_at,
            actions_done=int(account.warmup_actions_done or 0),
            warmup_days=int(settings.warmup_days or 7),
            actions_per_day=int(settings.warmup_actions_per_day or 8),
        )
        if settings.sandbox_mode:
            allowed, reason = True, ""
        else:
            allowed, reason = can_post_from_account(
                status=account.status,
                is_enabled=account.is_enabled,
                warmup=progress,
                posts_today=int(account.posts_today or 0),
                max_posts_per_day=int(settings.max_posts_per_account_per_day or 2),
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
        if not allowed:
            post.status = "held"
            post.hold_reason = reason
            continue
        if stagger and published_this_tick >= 1 and post.status != "processing":
            if post.status not in {"held", "failed"}:
                post.status = "pending"
                post.hold_reason = "Ждём паузу между аккаунтами"
            continue
        recipe = dict((video.uniqualization or {}).get(account.platform) or {})
        publisher_state = {
            key: value
            for key, value in (post.uniqualization_applied or {}).items()
            if key.startswith("ig_") or key.startswith("tiktok_")
        }
        variant = caption_variant(
            video.caption,
            account.platform,
            settings.product_url,
            seed=f"{video.id}:{account.id}",
            hashtags=list(video.hashtags or []),
        )
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
            )
        except PublisherError as exc:
            post.status = "failed"
            post.hold_reason = str(exc)[:500]
            account.last_error = str(exc)[:500]
            published_this_tick += 1
            continue
        status = str(result.get("status") or "posted")
        post.status = status
        post.external_id = str(result.get("external_id") or "")
        post.posted_url = str(result.get("posted_url") or "")
        post.caption_variant = variant
        applied = dict(recipe)
        if isinstance(result.get("publisher_state"), dict):
            applied.update(result["publisher_state"])
        post.uniqualization_applied = applied
        post.hold_reason = str(result.get("note") or "") or None
        if status in {"posted", "sandbox"}:
            post.posted_at = now_utc()
            account.last_posted_at = now_utc()
            account.posts_today = int(account.posts_today or 0) + 1
            account.last_error = None
            if account.status in {"connected", "ready", "warming"}:
                account.status = "ready"
        published_this_tick += 1
        bundle = result.get("token_bundle")
        if isinstance(bundle, dict) and bundle:
            from .content_factory_service import encrypt_json

            merged = decrypt_json(account.credentials_enc)
            merged.update({key: value for key, value in bundle.items() if value})
            account.credentials_enc = encrypt_json(merged)
    statuses = [item.status for item in existing.values()]
    if not statuses:
        video.status = "ready"
        extra["hold_reason"] = "Нет площадок для публикации"
        video.extra = extra
        video.last_error = None
        return
    if all(status in {"posted", "sandbox"} for status in statuses):
        video.status = "sandbox" if all(item == "sandbox" for item in statuses) else "posted"
        video.finished_at = now_utc()
        extra.pop("hold_reason", None)
        video.extra = extra
        video.last_error = None
        return
    if any(status in {"processing", "pending"} for status in statuses):
        video.status = "posting" if any(status == "processing" for status in statuses) else "ready"
        extra["hold_reason"] = "Публикация продолжается по аккаунтам с паузой"
        video.extra = extra
        video.last_error = None
        return
    if all(status == "held" for status in statuses):
        video.status = "ready"
        extra["hold_reason"] = next((item.hold_reason for item in existing.values() if item.hold_reason), "Постинг отложен")
        video.extra = extra
        video.last_error = None
        return
    if any(status in {"posted", "sandbox"} for status in statuses):
        video.status = "ready"
        extra["hold_reason"] = "Часть площадок готова, остальные ждут прогрева или лимита"
        video.extra = extra
        video.last_error = None
        return
    video.status = "failed"
    video.finished_at = now_utc()
    video.last_error = next((item.hold_reason for item in existing.values() if item.hold_reason), "Не удалось опубликовать")
    video.extra = extra


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
            account.warmup_completed_at = account.warmup_completed_at or now_utc()
            if account.status == "warming":
                account.status = "ready"
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
        day_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
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
            account.warmup_completed_at = now_utc()
            account.status = "ready"
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
            {"status": item.status, "posted_at": item.posted_at, "views": item.views}
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
        .order_by(CustomContentFactoryPost.posted_at.desc())
        .limit(5)
    )
    updated = 0
    for post in result.scalars().all():
        account = post.account
        if not account:
            continue
        stats = await fetch_post_analytics(
            platform=post.platform,
            credentials=decrypt_json(account.credentials_enc),
            external_id=post.external_id,
        )
        if not stats:
            continue
        post.views = int(stats.get("views") or 0)
        post.likes = int(stats.get("likes") or 0)
        post.comments = int(stats.get("comments") or 0)
        post.shares = int(stats.get("shares") or 0)
        post.saves = int(stats.get("saves") or 0)
        post.analytics_synced_at = now_utc()
        updated += 1
    return updated
