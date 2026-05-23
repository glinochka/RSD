"""In-process telephony metrics (stage 4 + latency budget stage 8)."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from time import monotonic

from .latency_budget import LATENCY_BUDGET_TARGETS_P90_MS, LatencyBudget, LatencyBudgetRollup, rollup_from_budget


@dataclass
class _TelephonyMetricsState:
    calls_started: int = 0
    calls_completed: int = 0
    transfers: int = 0
    stt_empty: int = 0
    turn_latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    latency_budget: LatencyBudgetRollup = field(default_factory=LatencyBudgetRollup)
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


def record_latency_budget(budget: LatencyBudget) -> None:
    with _lock:
        rollup_from_budget(budget, _state.latency_budget)
        if budget.e2r_ms is not None:
            _state.turn_latencies_ms.append(float(budget.e2r_ms))
        _state.updated_at = monotonic()


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def _budget_percentiles(rollup: LatencyBudgetRollup) -> dict[str, float | None]:
    return {
        "sip_p90_ms": _percentile(rollup.sip_ms, 90.0),
        "vad_p90_ms": _percentile(rollup.vad_ms, 90.0),
        "stt_final_p90_ms": _percentile(rollup.stt_final_ms, 90.0),
        "llm_ttft_p90_ms": _percentile(rollup.llm_ttft_ms, 90.0),
        "tts_ttfa_p90_ms": _percentile(rollup.tts_ttfa_ms, 90.0),
        "e2r_p90_ms": _percentile(rollup.e2r_ms, 90.0),
    }


def snapshot(*, alert_p95_ms: int, alert_e2r_p90_ms: int | None = None) -> dict:
    with _lock:
        latencies = list(_state.turn_latencies_ms)
        started = _state.calls_started
        completed = _state.calls_completed
        transfers = _state.transfers
        stt_empty = _state.stt_empty
        budget_rollup = _state.latency_budget

    p95 = _percentile(latencies, 95.0)
    budget_p90 = _budget_percentiles(budget_rollup)
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
    e2r_p90 = budget_p90.get("e2r_p90_ms")
    if alert_e2r_p90_ms and e2r_p90 is not None and e2r_p90 > alert_e2r_p90_ms:
        alerts.append(
            {
                "code": "e2r_p90_high",
                "message": f"e2r_p90 {e2r_p90:.0f}ms exceeds target {alert_e2r_p90_ms}ms",
                "severity": "warning",
            }
        )

    budget_table: dict[str, dict[str, float | int | None]] = {}
    for key, target in LATENCY_BUDGET_TARGETS_P90_MS.items():
        metric_key = key.replace("_ms", "_p90_ms")
        observed = budget_p90.get(metric_key)
        budget_table[key] = {
            "target_p90_ms": target,
            "observed_p90_ms": round(observed, 1) if observed is not None else None,
        }

    return {
        "calls_started": started,
        "calls_completed": completed,
        "turn_latency_p95_ms": round(p95, 1) if p95 is not None else None,
        "transfer_rate": round(transfer_rate, 4),
        "stt_empty_rate": round(stt_empty_rate, 4),
        "turn_samples": len(latencies),
        "latency_budget_samples": budget_rollup.samples,
        "latency_budget_p90": {k: round(v, 1) if v is not None else None for k, v in budget_p90.items()},
        "latency_budget_table": budget_table,
        "alerts": alerts,
    }


def prometheus_lines(*, alert_p95_ms: int, alert_e2r_p90_ms: int | None = None) -> str:
    snap = snapshot(alert_p95_ms=alert_p95_ms, alert_e2r_p90_ms=alert_e2r_p90_ms)
    lines: list[str] = []
    for name, value in (
        ("telephony_calls_started_total", snap["calls_started"]),
        ("telephony_calls_completed_total", snap["calls_completed"]),
        ("telephony_turn_latency_p95_ms", snap["turn_latency_p95_ms"]),
        ("telephony_transfer_rate", snap["transfer_rate"]),
        ("telephony_stt_empty_rate", snap["stt_empty_rate"]),
        ("telephony_latency_budget_samples", snap["latency_budget_samples"]),
    ):
        if value is None:
            continue
        lines.append(f"{name} {value}")
    for key, value in (snap.get("latency_budget_p90") or {}).items():
        if value is None:
            continue
        lines.append(f'telephony_{key}{{stage="streaming"}} {value}')
    for alert in snap.get("alerts") or []:
        code = str(alert.get("code") or "unknown")
        lines.append(f'telephony_alert{{code="{code}"}} 1')
    return "\n".join(lines) + ("\n" if lines else "")


def reset_for_tests() -> None:
    global _state
    with _lock:
        _state = _TelephonyMetricsState()
