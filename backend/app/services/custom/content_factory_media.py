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
        "Вертикальное видео, кинематографично, без водяных знаков и текста-меню."
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
    args = ["-y"]
    if shift_ms:
        args.extend(["-ss", f"{shift_ms}ms"])
    args.extend(
        [
            "-i",
            str(source),
            "-vf",
            vf,
            "-af",
            f"atempo={atempo:.4f}",
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
    try:
        _run_ffmpeg(args, timeout=180)
    except Exception as exc:
        logger.warning("Uniqualize ffmpeg failed, passthrough: %s", exc)
        shutil.copyfile(source, dest)
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
