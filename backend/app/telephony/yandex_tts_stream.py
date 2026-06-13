"""Yandex SpeechKit TTS v3 gRPC StreamSynthesis → PCM16 frames (8 kHz mono)."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import grpc

from ..config import settings
from .tts_service import map_voice_for_provider
_PCM16_FRAME_BYTES = 320  # 20 ms @ 8 kHz mono LINEAR16

logger = logging.getLogger(__name__)

_YANDEX_TTS_HOST = "tts.api.cloud.yandex.net:443"
_PROTO_PATH = Path(__file__).resolve().parent / "proto" / "yandex_tts_v3_minimal.proto"
_PCM_CHUNK_BYTES = 320  # 20 ms @ 8 kHz mono PCM16

_stub_lock = asyncio.Lock()
_stub_ready = False


def _ensure_stubs():
    global _stub_ready
    if _stub_ready:
        return
    from grpc_tools import protoc

    out_dir = Path(__file__).resolve().parent / "_grpc_gen"
    out_dir.mkdir(parents=True, exist_ok=True)
    init_file = out_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")

    result = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{_PROTO_PATH.parent}",
            f"--python_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            str(_PROTO_PATH),
        ]
    )
    if result != 0:
        raise RuntimeError("grpc_tools.protoc failed for yandex_tts_v3_minimal.proto")

    if str(out_dir) not in sys.path:
        sys.path.insert(0, str(out_dir))
    _stub_ready = True


def _metadata() -> list[tuple[str, str]]:
    api_key = (settings.YANDEX_SPEECHKIT_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("yandex_speechkit_key_missing")
    meta: list[tuple[str, str]] = [("authorization", f"Api-Key {api_key}")]
    folder_id = (settings.YANDEX_SPEECHKIT_FOLDER_ID or "").strip()
    if folder_id:
        meta.append(("x-folder-id", folder_id))
    return meta


# Voice mapping - supports both standard and premium :rc voices
def _get_effective_voice(voice: str) -> str:
    """Return effective voice name for Yandex TTS.
    
    Supports premium realistic conversation voices with :rc suffix:
    - alena:rc, jane:rc, omazh:rc, dasha:rc, marina:rc (female)
    - filipp:rc, ermil:rc, zahar:rc, alexander:rc, anton:rc, kirill:rc (male)
    
    Standard voices work without :rc suffix.
    """
    normalized = voice.strip().lower()
    
    # Check if premium :rc voice requested
    is_premium_rc = ":rc" in normalized
    
    # Extract base voice name
    base_voice = normalized.replace(":rc", "").replace(":premium", "").strip()
    
    # Valid voices for Yandex SpeechKit
    valid_standard_voices = {
        "alena", "jane", "omazh", "dasha", "marina",
        "filipp", "ermil", "zahar", "alexander", "anton", "kirill", "madi"
    }
    
    # Premium voices that support :rc mode
    premium_voices = {
        "alena", "jane", "omazh", "dasha", "marina",
        "filipp", "ermil", "zahar", "alexander", "anton", "kirill"
    }
    
    if base_voice not in valid_standard_voices:
        # Map common aliases
        voice_aliases = {
            "default": "alena",
            "neutral": "jane",
            "neutral-friendly": "alena",
            "female": "alena",
            "woman": "alena",
            "male": "filipp",
            "man": "filipp",
        }
        base_voice = voice_aliases.get(base_voice, "alena")
    
    # Return premium voice if requested and available
    if is_premium_rc and base_voice in premium_voices:
        return f"{base_voice}:rc"
    
    return base_voice


def _request_iter(pb2, text: str, voice: str):
    raw = pb2.RawAudio(audio_encoding=pb2.RawAudio.LINEAR16_PCM, sample_rate_hertz=8000)
    # Use effective voice (standard voices, no premium :rc suffix)
    effective_voice = _get_effective_voice(voice)
    logger.debug("yandex_tts using voice=%s (input=%s)", effective_voice, voice)
    opts = pb2.SynthesisOptions(
        voice=effective_voice,
        speed=1.0,
        output_audio_spec=pb2.AudioFormatOptions(raw_audio=raw),
    )
    yield pb2.StreamSynthesisRequest(options=opts)
    yield pb2.StreamSynthesisRequest(synthesis_input=pb2.SynthesisInput(text=text))
    yield pb2.StreamSynthesisRequest(force_synthesis=pb2.ForceSynthesisEvent())


def _stream_pcm_chunks(text: str, voice: str, timeout: float) -> list[bytes]:
    _ensure_stubs()
    import yandex_tts_v3_minimal_pb2 as pb2  # type: ignore[import-untyped]
    import yandex_tts_v3_minimal_pb2_grpc as pb2_grpc  # type: ignore[import-untyped]

    creds = grpc.ssl_channel_credentials()
    channel = grpc.secure_channel(_YANDEX_TTS_HOST, creds)
    stub = pb2_grpc.SynthesizerStub(channel)
    pcm_parts: list[bytes] = []
    for resp in stub.StreamSynthesis(
        _request_iter(pb2, text, voice),
        metadata=_metadata(),
        timeout=timeout,
    ):
        data = resp.audio_chunk.data if resp.audio_chunk else b""
        if data:
            pcm_parts.append(bytes(data))
    channel.close()
    return pcm_parts


def _convert_be_to_le(pcm16_be: bytes) -> bytes:
    """Convert big-endian PCM16 to little-endian. Yandex SpeechKit returns BE."""
    if not pcm16_be or len(pcm16_be) < 2:
        return pcm16_be
    # Swap every 2 bytes: ABCD -> BADC
    le = bytearray(pcm16_be)
    for i in range(0, len(le) - 1, 2):
        le[i], le[i + 1] = le[i + 1], le[i]
    return bytes(le)


def _pcm16_stats_as_le(buf: bytes) -> tuple[float, float]:
    """Return (mean_abs, clipped_ratio) for PCM16 interpreted as LE."""
    if len(buf) < 2:
        return 0.0, 0.0
    sample_count = len(buf) // 2
    if sample_count <= 0:
        return 0.0, 0.0
    abs_sum = 0
    clipped = 0
    for i in range(0, sample_count * 2, 2):
        s = int.from_bytes(buf[i : i + 2], byteorder="little", signed=True)
        a = abs(s)
        abs_sum += a
        if a >= 28000:
            clipped += 1
    return abs_sum / sample_count, clipped / sample_count


def _normalize_pcm16_to_le(part: bytes) -> bytes:
    """
    Normalize incoming PCM16 chunk to little-endian.

    Some providers/environments may deliver LINEAR16 either in LE or BE.
    We score both interpretations and pick the one with less clipping/noise.
    """
    if not part or len(part) < 2:
        return part
    even = part[: (len(part) // 2) * 2]
    if not even:
        return even

    # Candidate A: keep as-is (assume LE)
    le_buf = even
    le_mean_abs, le_clipped_ratio = _pcm16_stats_as_le(le_buf)

    # Candidate B: byte-swap (assume source BE)
    swapped = _convert_be_to_le(even)
    be_mean_abs, be_clipped_ratio = _pcm16_stats_as_le(swapped)

    # Prefer the candidate with lower clipping ratio; tie-breaker by mean abs.
    # Wrong endianness typically shows very high amplitude/clipping and sounds like crackle.
    if be_clipped_ratio + 1e-9 < le_clipped_ratio:
        return swapped
    if le_clipped_ratio + 1e-9 < be_clipped_ratio:
        return le_buf
    return swapped if be_mean_abs < le_mean_abs else le_buf


async def stream_yandex_v3_pcm16_frames(
    text: str,
    *,
    voice_id: str,
    lang: str,
    timeout: float,
) -> AsyncIterator[bytes]:
    del lang
    voice = map_voice_for_provider("yandex", voice_id)
    effective_voice = _get_effective_voice(voice)
    logger.info(
        "yandex_tts_stream: text_len=%d voice_id=%s mapped=%s effective=%s timeout=%.1f",
        len(text), voice_id, voice, effective_voice, timeout
    )
    async with _stub_lock:
        pcm_parts = await asyncio.to_thread(_stream_pcm_chunks, text, effective_voice, timeout)

    pcm_buf = bytearray()
    endian_logged = False
    for part in pcm_parts:
        part_le = _normalize_pcm16_to_le(part)
        if not endian_logged and part and len(part) >= 2:
            raw_even = part[: (len(part) // 2) * 2]
            le_mean_abs_raw, le_clip_raw = _pcm16_stats_as_le(raw_even)
            swapped = _convert_be_to_le(raw_even)
            le_mean_abs_swapped, le_clip_swapped = _pcm16_stats_as_le(swapped)
            chosen = "swapped_be_to_le" if part_le == swapped else "as_is_le"
            logger.info(
                "yandex_tts_stream endian normalize: chosen=%s raw_mean=%.1f raw_clip=%.3f "
                "swap_mean=%.1f swap_clip=%.3f bytes=%d",
                chosen,
                le_mean_abs_raw,
                le_clip_raw,
                le_mean_abs_swapped,
                le_clip_swapped,
                len(raw_even),
            )
            endian_logged = True
        pcm_buf.extend(part_le)
        while len(pcm_buf) >= _PCM16_FRAME_BYTES:
            segment = bytes(pcm_buf[:_PCM16_FRAME_BYTES])
            del pcm_buf[:_PCM16_FRAME_BYTES]
            yield segment

    if pcm_buf:
        tail = bytes(pcm_buf)
        if len(tail) % 2 == 1:
            tail = tail[:-1]
        if tail:
            if len(tail) < _PCM16_FRAME_BYTES:
                tail += b"\x00" * (_PCM16_FRAME_BYTES - len(tail))
            yield tail
