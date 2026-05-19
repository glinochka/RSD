"""In-memory partial STT buffer per call (stage 5). Optional Redis via bridge session."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_PARTIAL_TTL_SEC = 600


@dataclass
class PartialSnapshot:
    transcript: str = ""
    confidence: float | None = None
    updated_at: float = field(default_factory=time.time)
    started_at: float = field(default_factory=time.time)
    partial_count: int = 0
    backchannel_sent: bool = False


_store: dict[int, PartialSnapshot] = {}


def _prune() -> None:
    now = time.time()
    stale = [cid for cid, snap in _store.items() if now - snap.updated_at > _PARTIAL_TTL_SEC]
    for cid in stale:
        _store.pop(cid, None)


def record_partial(
    call_db_id: int,
    *,
    transcript: str,
    is_final: bool,
    confidence: float | None = None,
) -> PartialSnapshot:
    _prune()
    snap = _store.get(call_db_id)
    if snap is None:
        snap = PartialSnapshot(started_at=time.time())
    text = (transcript or "").strip()
    if text:
        snap.transcript = text
        snap.partial_count += 1
    if confidence is not None:
        snap.confidence = confidence
    snap.updated_at = time.time()
    _store[call_db_id] = snap

    if not is_final:
        logger.debug(
            "telephony partial stt call_db_id=%s len=%s partials=%s",
            call_db_id,
            len(snap.transcript),
            snap.partial_count,
        )
    else:
        logger.info(
            "telephony partial stt final call_db_id=%s len=%s partials=%s",
            call_db_id,
            len(snap.transcript),
            snap.partial_count,
        )
    return snap


def get_partial(call_db_id: int) -> PartialSnapshot | None:
    _prune()
    return _store.get(call_db_id)


def clear_partial(call_db_id: int) -> None:
    _store.pop(call_db_id, None)


def utterance_duration_ms(call_db_id: int) -> int:
    snap = get_partial(call_db_id)
    if snap is None:
        return 0
    return int(max(0, (time.time() - snap.started_at) * 1000))


def mark_backchannel_sent(call_db_id: int) -> None:
    snap = _store.get(call_db_id)
    if snap is not None:
        snap.backchannel_sent = True


def should_suggest_backchannel(call_db_id: int, *, min_ms: int) -> bool:
    snap = get_partial(call_db_id)
    if snap is None or snap.backchannel_sent or not snap.transcript.strip():
        return False
    return utterance_duration_ms(call_db_id) >= max(1000, min_ms)
