"""Yandex SpeechKit TTS v3 gRPC StreamSynthesis → PCM16 frames (8 kHz mono)."""

from __future__ import annotations

import array
import asyncio
import logging
import math
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


# Voice mapping - using standard voices (premium :rc voices require special access)
# Standard voices work with regular Yandex SpeechKit API access
def _get_effective_voice(voice: str) -> str:
    """Return effective voice name for Yandex TTS."""
    normalized = voice.strip().lower()
    # Remove :rc or :premium suffix if present - we use standard voices
    base_voice = normalized.replace(":rc", "").replace(":premium", "")
    # Valid standard voices for Yandex SpeechKit
    valid_voices = {
        "alena", "jane", "omazh", "dasha", "marina",
        "filipp", "ermil", "zahar", "alexander", "anton", "kirill", "madi"
    }
    if base_voice in valid_voices:
        return base_voice
    # Default fallback
    return "alena"


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


def _normalize_pcm16_volume(pcm16_le: bytes, target_db: float = -14.0) -> bytes:
    """
    Normalize PCM16 audio to target dB level.
    Prevents quiet/robotic sound on telephone lines.
    """
    if not pcm16_le or len(pcm16_le) < 2:
        return pcm16_le
    
    # Convert bytes to array of int16 samples (signed short = 'h')
    samples = array.array('h', pcm16_le)
    if len(samples) == 0:
        return pcm16_le
    
    # Find peak amplitude
    peak = max(abs(s) for s in samples)
    if peak == 0:
        return pcm16_le
    
    # Calculate current dB and gain needed
    current_db = 20 * math.log10(peak / 32768.0)
    gain_db = target_db - current_db
    gain = math.pow(10, gain_db / 20)
    
    # Limit gain to prevent clipping
    max_gain = 32767.0 / peak
    gain = min(gain, max_gain, 10.0)  # Cap at 10x (20dB)
    
    if gain > 1.0 or gain < 1.0:
        # Apply gain
        for i in range(len(samples)):
            sample = int(samples[i] * gain)
            sample = max(-32768, min(32767, sample))  # Clip
            samples[i] = sample
    
    return samples.tobytes()


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
    for part in pcm_parts:
        # Yandex SpeechKit returns PCM16 in native format (little-endian on most systems)
        # Just normalize volume for telephone clarity
        part_normalized = _normalize_pcm16_volume(part, target_db=-14.0)
        pcm_buf.extend(part_normalized)
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
