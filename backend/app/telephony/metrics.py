"""In-process telephony metrics (MVP — stage 4)."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from time import monotonic


@dataclass
class _TelephonyMetricsState:
    calls_started: int = 0
    calls_completed: int = 0
    transfers: int = 0
    stt_empty: int = 0
    turn_latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    updated_at: float = field(default_factory=monotonic)


_lock = threading.Lock()
_state = _TelephonyMetricsState()


def record_call_started() -> None:
    with _lock:
        _state.calls_started += 1
        _state.updated_at = monotonic()


def record_call_completed(*, transferred: bool = False) -> None:
    with _lock:
        _state.calls_completed += 1
        if transferred:
            _state.transfers += 1
        _state.updated_at = monotonic()


def record_stt_empty() -> None:
    with _lock:
        _state.stt_empty += 1
        _state.updated_at = monotonic()


def record_turn_latency_ms(latency_ms: int) -> None:
    if latency_ms < 0:
        return
    with _lock:
        _state.turn_latencies_ms.append(float(latency_ms))
        _state.updated_at = monotonic()


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def snapshot(*, alert_p95_ms: int) -> dict:
    with _lock:
        latencies = list(_state.turn_latencies_ms)
        started = _state.calls_started
        completed = _state.calls_completed
        transfers = _state.transfers
        stt_empty = _state.stt_empty

    p95 = _percentile(latencies, 95.0)
    transfer_rate = (transfers / completed) if completed > 0 else 0.0
    stt_empty_rate = (stt_empty / max(1, len(latencies))) if latencies else 0.0

    alerts: list[dict] = []
    if p95 is not None and p95 > alert_p95_ms:
        alerts.append(
            {
                "code": "turn_latency_p95_high",
                "message": f"turn_latency_p95 {p95:.0f}ms exceeds threshold {alert_p95_ms}ms",
                "severity": "warning",
            }
        )

    return {
        "calls_started": started,
        "calls_completed": completed,
        "turn_latency_p95_ms": round(p95, 1) if p95 is not None else None,
        "transfer_rate": round(transfer_rate, 4),
        "stt_empty_rate": round(stt_empty_rate, 4),
        "turn_samples": len(latencies),
        "alerts": alerts,
    }


def reset_for_tests() -> None:
    global _state
    with _lock:
        _state = _TelephonyMetricsState()
