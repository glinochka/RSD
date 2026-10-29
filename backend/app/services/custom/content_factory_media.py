"""Clip planning, download, ffmpeg stitch and uniqualization for the content factory."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ...config import settings

logger = logging.getLogger(__name__)

KLING_MAX_SECONDS = 8
KLING_MIN_SECONDS = 5
MAX_CLIPS = 8
ASPECT_PIXELS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


def plan_clip_durations(duration_seconds: int) -> list[int]:
    """Split a 30–60s brief into Kling-sized clips (5–8s), max 8 clips."""
    total = max(KLING_MIN_SECONDS, min(int(duration_seconds or 30), KLING_MAX_SECONDS * MAX_CLIPS))
    count = max(1, min(MAX_CLIPS, (total + KLING_MAX_SECONDS - 1) // KLING_MAX_SECONDS))
    base, remainder = divmod(total, count)
    while count > 1 and base < KLING_MIN_SECONDS:
        count -= 1
        base, remainder = divmod(total, count)
    parts = [base + (1 if index < remainder else 0) for index in range(count)]
    return [max(KLING_MIN_SECONDS, min(KLING_MAX_SECONDS, part)) if count > 1 else min(KLING_MAX_SECONDS, total) for part in parts]


def align_storyboard(scenes: list[Any] | None, durations: list[int]) -> list[dict[str, Any]]:
    source = [item if isinstance(item, dict) else {} for item in (scenes or [])]
    start = 0
    framed: list[dict[str, Any]] = []
    for index, duration in enumerate(durations):
        scene = source[index] if index < len(source) else (source[-1] if source else {})
        framed.append(
            {
                "t": start,
                "duration": duration,
                "visual": str(scene.get("visual") or "")[:500],
                "voiceover": str(scene.get("voiceover") or "")[:500],
            }
        )
        start += duration
    return framed


def clip_prompt(
    *,
    settings_row: Any,
    video: Any,
    clip: dict[str, Any],
    index: int,
    total: int,
) -> str:
    product = str(getattr(settings_row, "product_name", "") or "продукт")
    visual = str(clip.get("visual") or "")
    voice = str(clip.get("voiceover") or "")
    role = "хук, первые секунды, стоп-кадр"
    if index == total - 1 and total > 1:
        role = "финал и CTA, тот же персонаж и свет"
    elif index > 0:
        role = "продолжение той же сцены, тот же персонаж, одежда и палитра"
    return (
        f"Клип {index + 1}/{total} цельного ролика {getattr(video, 'duration_seconds', 0)}с, "
        f"кадр {getattr(video, 'aspect_ratio', '9:16')}, длительность этого куска {clip.get('duration')}с.\n"
        f"Стиль: {getattr(video, 'visual_style', 'realism')}. Продукт: {product}.\n"
        f"Роль куска: {role}.\n"
        f"Хук всего ролика: {getattr(video, 'hook', '')}\n"
        f"Визуал: {visual}\n"
        f"Голос за кадром: {voice}\n"
        "Сними визуал буквально: если там сатирическая подмена объекта новости, не заменяй её презентацией продукта.\n"
        "Вертикальное видео, фотореализм, без водяных знаков, субтитров и логотипов."
    )


def ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def media_root() -> Path:
    path = Path(settings.MEDIA_ROOT).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def video_dir(automation_id: int, video_id: int) -> Path:
    path = media_root() / "content_factory" / str(automation_id) / str(video_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_media_path(path: Path) -> str:
    return path.resolve().relative_to(media_root()).as_posix()


def public_media_url(relative_or_path: str | Path) -> str:
    if isinstance(relative_or_path, Path):
        relative = relative_media_path(relative_or_path)
    else:
        text = str(relative_or_path or "").replace("\\", "/").strip()
        if text.startswith("http://") or text.startswith("https://"):
            return text
        relative = text.split("/media/", 1)[-1].lstrip("/") if "/media/" in text else text.lstrip("/")
    base = (settings.BASE_URL or "").rstrip("/")
    if base:
        return f"{base}/media/{relative}"
    return f"/media/{relative}"


def local_path_from_url(url: str | None) -> Path | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.exists() and candidate.is_file():
        return candidate
    parsed = urlparse(raw)
    path = parsed.path or raw
    if "/media/" in path:
        relative = path.split("/media/", 1)[1]
        full = (media_root() / relative).resolve()
        if str(full).startswith(str(media_root())) and full.exists():
            return full
    relative = path.lstrip("/")
    full = (media_root() / relative).resolve()
    if str(full).startswith(str(media_root())) and full.exists():
        return full
    return None


async def download_to_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    local = local_path_from_url(url)
    if local:
        if local.resolve() != dest.resolve():
            shutil.copyfile(local, dest)
        return dest
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url)
        if not response.is_success:
            raise RuntimeError(f"Не удалось скачать клип: HTTP {response.status_code}")
        if not response.content:
            raise RuntimeError("Пустой файл клипа")
        dest.write_bytes(response.content)
    return dest


def _run_ffmpeg(args: list[str], *, timeout: int = 180) -> None:
    binary = ffmpeg_bin()
    if not binary:
        raise RuntimeError("ffmpeg не найден — склейка ролика недоступна")
    completed = subprocess.run(
        [binary, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "")[-500:]
        raise RuntimeError(f"ffmpeg failed: {detail}")


def concat_clips(clip_paths: list[Path], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = [path for path in clip_paths if path.exists() and path.stat().st_size > 0]
    if not existing:
        raise RuntimeError("Нет клипов для склейки")
    if len(existing) == 1:
        if existing[0].resolve() != dest.resolve():
            shutil.copyfile(existing[0], dest)
        return dest
    if not ffmpeg_bin():
        shutil.copyfile(existing[0], dest)
        logger.warning("ffmpeg missing, using first clip as master")
        return dest
    listing = dest.parent / "concat.txt"
    lines = []
    for path in existing:
        escaped = path.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines), encoding="utf-8")
    _run_ffmpeg(
        [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest


def write_thumbnail(source: Path, dest: Path) -> Path | None:
    if not ffmpeg_bin() or not source.exists():
        return None
    try:
        _run_ffmpeg(
            ["-y", "-ss", "0.4", "-i", str(source), "-frames:v", "1", "-q:v", "3", str(dest)],
            timeout=30,
        )
        return dest if dest.exists() else None
    except Exception as exc:
        logger.info("Thumbnail skipped: %s", exc)
        return None


def uniqualize_file(*, source: Path, dest: Path, recipe: dict[str, Any], aspect_ratio: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if recipe.get("passthrough") or not ffmpeg_bin():
        shutil.copyfile(source, dest)
        return dest
    width, height = ASPECT_PIXELS.get(aspect_ratio or "9:16", (1080, 1920))
    speed = float(recipe.get("speed") or 1.0)
    speed = max(0.9, min(1.1, speed))
    crop_pct = float(recipe.get("crop_pct") or 0.0)
    crop_ratio = max(0.92, min(0.999, 1.0 - (crop_pct / 100.0)))
    temp = float(recipe.get("color_temp") or 0)
    brightness = max(-0.06, min(0.06, temp / 3000.0))
    saturation = max(0.9, min(1.15, 1.0 + (temp / 2500.0)))
    shift_ms = max(0, min(400, int(recipe.get("intro_frame_shift_ms") or 0)))
    filters = [
        f"crop=iw*{crop_ratio:.4f}:ih*{crop_ratio:.4f}",
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"setpts=PTS/{speed:.4f}",
        f"eq=brightness={brightness:.4f}:saturation={saturation:.4f}",
    ]
    if recipe.get("grain"):
        filters.append("noise=alls=6:allf=t")
    if recipe.get("mirror_safe"):
        filters.append("hflip")
    vf = ",".join(filters)
    atempo = max(0.5, min(2.0, speed))
    cents = max(-200, min(200, int(recipe.get("audio_pitch_cents") or 0)))
    ratio = 2 ** (cents / 1200.0)
    pitch_fix = 1.0 / ratio if ratio else 1.0
    combined = max(0.5, min(2.0, atempo * pitch_fix))
    duck_db = max(0.0, min(6.0, float(recipe.get("audio_duck_db") or 0.0)))
    loudness = 10 ** (-duck_db / 20.0)
    audio_filter = (
        f"asetrate={int(44100 * ratio)},aresample=44100,"
        f"atempo={combined:.4f},volume={loudness:.3f}"
    )
    base = ["-y"]
    if shift_ms:
        base.extend(["-ss", f"{shift_ms}ms"])
    base.extend(["-i", str(source), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    with_audio = [*base, "-af", audio_filter, "-c:a", "aac", str(dest)]
    silent = [*base, "-an", str(dest)]
    try:
        _run_ffmpeg(with_audio, timeout=180)
    except Exception as exc:
        try:
            _run_ffmpeg(silent, timeout=180)
        except Exception:
            logger.warning("Uniqualize ffmpeg failed, passthrough: %s", exc)
            shutil.copyfile(source, dest)
    return dest


def slides_to_mp4(slide_paths: list[Path], dest: Path, *, seconds: float = 2.4) -> Path:
    """Still frames become a vertical video that swipes on its own. YouTube has no photo carousel."""
    existing = [path for path in slide_paths if path.exists() and path.stat().st_size > 0]
    if len(existing) < 2:
        raise RuntimeError("Для слайд-шоу нужно хотя бы два кадра")
    if not ffmpeg_bin():
        raise RuntimeError("ffmpeg не найден — YouTube-слайдшоу из карусели не собрать")
    dest.parent.mkdir(parents=True, exist_ok=True)
    hold = max(1.2, min(float(seconds), 4.0))
    args = ["-y"]
    filters = []
    for index, path in enumerate(existing):
        args.extend(["-loop", "1", "-t", f"{hold:.2f}", "-i", str(path)])
        filters.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{index}]"
        )
    concat = "".join(f"[v{index}]" for index in range(len(existing)))
    filters.append(f"{concat}concat=n={len(existing)}:v=1:a=0[v]")
    args.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    _run_ffmpeg(args, timeout=180)
    return dest


DEFAULT_GROK_CAROUSEL_BRIEF = (
    "Стиль как у живой фото-карусели Grok Bot: вертикальные кадры 9:16, "
    "один герой и один свет на всю пачку, без текста, логотипов и водяных знаков."
)
GROK_CAROUSEL_MODEL = "grok-4.7"


def factory_grok_bot_id(automation_id: int) -> str:
    return f"cf-carousel-{int(automation_id)}"


def grok_carousel_message(
    *,
    company: str,
    description: str,
    audience: str,
    niche: str,
    brief: str,
    avoid: list[str] | None = None,
    follow_up: bool = False,
) -> str:
    """One message. The agent picks the theme and calls Imagine itself."""
    skipped = [str(item).strip() for item in (avoid or []) if str(item).strip()]
    style = str(brief or "").strip() or DEFAULT_GROK_CAROUSEL_BRIEF
    if follow_up:
        text = (
            "Сделай новую фото-карусель с другой тематикой и другим сценарием. "
            "Снова 6 или 7 отдельных вертикальных кадров 9:16, в порядке свайпа. "
            "Не повторяй прошлые темы. Без текста на фото. "
            "Каждый кадр — отдельный вызов картинки, не коллаж."
        )
    else:
        text = (
            f"Стиль и дизайн:\n{style}\n\n"
            f"Компания: {company or 'не указана'}.\n"
            f"Что делаем: {description or 'не указано'}.\n"
            f"Кому: {audience or 'не указано'}. Ниша: {niche or 'не указана'}.\n\n"
            "Выбери тематику и сделай фото-карусель для контент-завода. "
            "Сразу 6 или 7 хороших вертикальных кадров 9:16, которые уже можно заливать. "
            "Порядок — порядок свайпа: первый кадр цепляет, последний закрывает мысль. "
            "Без текста, логотипов и водяных знаков. "
            "Каждый кадр рисуй отдельным вызовом картинки, не склеивай в один коллаж."
        )
    if skipped:
        text += "\nНе повторяй: " + "; ".join(skipped[:8])
    text += "\nВ тексте ответа коротко назови тему и дай подпись к посту. Картинки важнее текста."
    return text


def grok_agent_pack(payload: dict[str, Any]) -> dict[str, Any]:
    """Images stay in the order the agent emitted them."""
    import base64

    images: list[dict[str, str]] = []
    texts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "image_generation_call" and str(item.get("status") or "completed") == "completed":
            raw = str(item.get("result") or "").strip()
            if raw.startswith("data:") and "," in raw:
                raw = raw.split(",", 1)[1]
            if raw:
                images.append({"b64": raw, "prompt": str(item.get("prompt") or "")[:500]})
        elif item.get("type") == "message":
            content = item.get("content")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, str):
                        texts.append(part)
                    elif isinstance(part, dict):
                        texts.append(str(part.get("text") or ""))
    decoded: list[dict[str, Any]] = []
    for image in images:
        try:
            blob = base64.b64decode(image["b64"])
        except Exception:
            continue
        if blob:
            decoded.append({"bytes": blob, "prompt": image["prompt"]})
    return {
        "images": decoded,
        "text": "\n".join(part.strip() for part in texts if str(part).strip()).strip(),
        "response_id": str(payload.get("id") or "").strip(),
    }


async def generate_grok_carousel_pack(
    *,
    api_key: str,
    company: str,
    description: str,
    audience: str,
    niche: str,
    brief: str,
    avoid: list[str] | None,
    previous_response_id: str,
    folder: Path,
) -> dict[str, Any]:
    """One Responses call. Grok writes the prompts and generates the pack."""
    folder.mkdir(parents=True, exist_ok=True)
    thread = str(previous_response_id or "").strip()

    async def _ask(follow_up: bool, response_id: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": GROK_CAROUSEL_MODEL,
            "input": grok_carousel_message(
                company=company,
                description=description,
                audience=audience,
                niche=niche,
                brief=brief,
                avoid=avoid,
                follow_up=follow_up,
            ),
            "tools": [{"type": "image_generation", "action": "auto"}],
        }
        if follow_up and response_id:
            body["previous_response_id"] = response_id
        async with httpx.AsyncClient(timeout=360.0) as client:
            response = await client.post(
                "https://api.x.ai/v1/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Grok Bot: HTTP {response.status_code} {response.text[:240]}")
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            raise RuntimeError("Grok Bot вернул пустой ответ")
        return grok_agent_pack(payload)

    try:
        pack = await _ask(bool(thread), thread)
    except RuntimeError:
        if not thread:
            raise
        pack = await _ask(False, "")
    images = pack["images"]
    if len(images) < 4:
        raise RuntimeError(f"Grok Bot вернул {len(images)} кадров, для карусели нужно 6–7")
    paths: list[Path] = []
    prompts: list[str] = []
    for index, image in enumerate(images[:7]):
        dest = folder / f"slide-{index:02d}.png"
        dest.write_bytes(image["bytes"])
        paths.append(dest)
        prompts.append(image["prompt"])
    return {
        "paths": paths,
        "prompts": prompts,
        "text": pack["text"],
        "response_id": pack["response_id"],
        "continued": bool(thread),
    }


async def generate_slide_png(*, provider: str, model: str, api_key: str, prompt: str, dest: Path) -> Path:
    from openai import AsyncOpenAI

    spec = {
        "chatgpt": "https://api.openai.com/v1",
        "grok": "https://api.x.ai/v1",
    }
    base = spec.get(provider)
    if not base or not api_key:
        raise RuntimeError("Для карусели нужен ключ ChatGPT или Grok")
    client = AsyncOpenAI(api_key=api_key, base_url=base, timeout=90.0, max_retries=0)
    kwargs = {"model": model or ("grok-imagine-image-2.0" if provider == "grok" else "gpt-image-2.5-flare"), "prompt": prompt[:900]}
    if provider == "chatgpt":
        kwargs["size"] = "1024x1536"
    try:
        result = await client.images.generate(**kwargs)
    except Exception:
        result = await client.images.generate(model=kwargs["model"], prompt=kwargs["prompt"])
    data = (result.data or [None])[0]
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = getattr(data, "b64_json", None)
    if raw:
        import base64

        dest.write_bytes(base64.b64decode(raw))
        return dest
    url = getattr(data, "url", None)
    if not url:
        raise RuntimeError("Модель картинок вернула пустой кадр")
    await download_to_file(url, dest)
    return dest


def voiceover_lines(video: Any) -> str:
    parts: list[str] = []
    hook = str(getattr(video, "hook", "") or "").strip()
    if hook:
        parts.append(hook)
    for scene in getattr(video, "storyboard", None) or []:
        if not isinstance(scene, dict):
            continue
        line = str(scene.get("voiceover") or "").strip()
        if line and line not in parts:
            parts.append(line)
    return "\n".join(parts)[:2400]


def write_music_bed(dest: Path, *, seconds: float = 8.0, seed: str = "bed") -> Path:
    """Original instrumental loop. No third-party track, so it can ship with the slideshow."""
    import hashlib
    import math
    import struct
    import wave

    rate = 22050
    length = max(4.0, min(float(seconds), 16.0))
    count = int(rate * length)
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    root = 196.0 * (2 ** ((digest[0] % 5) / 12.0))
    scale = (0, 3, 5, 7, 10, 7, 5, 3)
    frames = bytearray()
    for index in range(count):
        moment = index / rate
        step = int(moment / 0.5) % len(scale)
        freq = root * (2 ** (scale[step] / 12.0))
        envelope = math.exp(-((moment % 0.5) * 5.5))
        sample = 0.22 * envelope * math.sin(2 * math.pi * freq * moment)
        sample += 0.07 * math.sin(2 * math.pi * (root / 2.0) * moment)
        clipped = max(-1.0, min(1.0, sample))
        frames += struct.pack("<h", int(clipped * 26000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)
    return dest


def mix_soundtrack(
    *,
    video: Path,
    dest: Path,
    bed: Path | None = None,
    voice: Path | None = None,
    bed_volume: float = 0.32,
    voice_volume: float = 1.0,
) -> Path:
    """Lay voice and a looping bed under a silent slideshow or an existing clip."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tracks: list[tuple[Path, float, bool]] = []
    if voice and voice.exists() and voice.stat().st_size > 0:
        tracks.append((voice, max(0.0, min(1.5, voice_volume)), False))
    if bed and bed.exists() and bed.stat().st_size > 0:
        tracks.append((bed, max(0.0, min(1.0, bed_volume)), True))
    if not tracks:
        if video.resolve() != dest.resolve():
            shutil.copyfile(video, dest)
        return dest
    if not ffmpeg_bin():
        raise RuntimeError("ffmpeg не найден — музыку не наложить")
    args = ["-y", "-i", str(video)]
    filters: list[str] = []
    labels: list[str] = []
    for index, (path, volume, loop) in enumerate(tracks, start=1):
        if loop:
            args.extend(["-stream_loop", "-1"])
        args.extend(["-i", str(path)])
        label = f"a{index}"
        filters.append(f"[{index}:a]volume={volume:.3f}[{label}]")
        labels.append(f"[{label}]")
    if len(labels) == 1:
        mixed = labels[0]
    else:
        filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0[mix]")
        mixed = "[mix]"
    args.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v",
            "-map",
            mixed,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    _run_ffmpeg(args, timeout=180)
    return dest


async def synthesize_voiceover(*, api_key: str, voice_id: str, model_id: str, text: str, dest: Path) -> Path:
    speech = str(text or "").strip()
    if not api_key or not speech:
        raise RuntimeError("Нет текста или ключа для озвучки")
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
            json={"text": speech[:2400], "model_id": model_id or "eleven_multilingual_v2"},
        )
    if not response.is_success or not response.content:
        raise RuntimeError(f"ElevenLabs: HTTP {response.status_code} {response.text[:180]}")
    dest.write_bytes(response.content)
    return dest


async def resolve_video_bytes(video_url: str | None) -> bytes:
    local = local_path_from_url(video_url)
    if local:
        data = local.read_bytes()
        if data:
            return data
    url = str(video_url or "").strip()
    if not url.startswith("http"):
        raise RuntimeError("Нет готового файла ролика")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url)
        if not response.is_success:
            raise RuntimeError(f"Не удалось скачать ролик: HTTP {response.status_code}")
        if not response.content:
            raise RuntimeError("Пустой файл ролика")
        return response.content
