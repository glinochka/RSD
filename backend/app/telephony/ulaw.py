"""G.711 μ-law encode/decode for 8 kHz telephony (stage 5)."""

from __future__ import annotations

import audioop


def pcm16_to_ulaw(pcm: bytes) -> bytes:
    """PCM16 little-endian mono → μ-law."""
    if not pcm:
        return b""
    return audioop.lin2ulaw(pcm, 2)


def ulaw_to_pcm16(ulaw: bytes) -> bytes:
    if not ulaw:
        return b""
    return audioop.ulaw2lin(ulaw, 2)


def chunk_ulaw_frames(ulaw: bytes, *, frame_bytes: int = 160) -> list[bytes]:
    """Split μ-law buffer into ~20 ms frames (160 bytes @ 8 kHz)."""
    if frame_bytes <= 0:
        return [ulaw] if ulaw else []
    return [ulaw[i : i + frame_bytes] for i in range(0, len(ulaw), frame_bytes) if ulaw[i : i + frame_bytes]]
