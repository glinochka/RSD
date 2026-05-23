"""Latency budget for PSTN streaming (stage 8).

Fields persisted on ``agent_telephony_calls.metadata_`` under ``latency_budget`` and
aggregated in-process for ``/api/internal/telephony/metrics``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

LATENCY_BUDGET_META_KEY = "latency_budget"
LATENCY_BUDGET_HISTORY_KEY = "latency_budget_turns"
LATENCY_BUDGET_TARGETS_P90_MS = {
    "sip_ms": 1200,
    "vad_ms": 450,
    "stt_final_ms": 400,
    "llm_ttft_ms": 300,
    "tts_ttfa_ms": 150,
    "crm_execute_ms": 1500,
    "e2r_ms": 850,
}


@dataclass
class LatencyBudget:
    sip_ms: int | None = None
    vad_ms: int | None = None
    stt_final_ms: int | None = None
    llm_ttft_ms: int | None = None
    tts_ttfa_ms: int | None = None
    crm_execute_ms: int | None = None
    e2r_ms: int | None = None

    def to_dict(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for key, value in asdict(self).items():
            if value is not None and int(value) >= 0:
                out[key] = int(value)
        return out


@dataclass
class LatencyBudgetRollup:
    samples: int = 0
    sip_ms: list[float] = field(default_factory=list)
    vad_ms: list[float] = field(default_factory=list)
    stt_final_ms: list[float] = field(default_factory=list)
    llm_ttft_ms: list[float] = field(default_factory=list)
    tts_ttfa_ms: list[float] = field(default_factory=list)
    crm_execute_ms: list[float] = field(default_factory=list)
    e2r_ms: list[float] = field(default_factory=list)


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def estimate_vad_ms(*, stt_final_ms: int | None, vad_speech_ratio: float | None) -> int | None:
    if stt_final_ms is None or vad_speech_ratio is None:
        return None
    ratio = max(0.0, min(1.0, float(vad_speech_ratio)))
    silence_ms = int(round(stt_final_ms * (1.0 - ratio)))
    return max(0, silence_ms)


def budget_from_gateway(inner: dict[str, Any]) -> LatencyBudget:
    metrics = inner.get("metrics") if isinstance(inner.get("metrics"), dict) else inner
    stt_final_ms = _positive_int(metrics.get("stt_final_ms"))
    vad_ratio_raw = metrics.get("vad_speech_ratio")
    vad_ratio = float(vad_ratio_raw) if vad_ratio_raw is not None else None
    return LatencyBudget(
        stt_final_ms=stt_final_ms,
        vad_ms=estimate_vad_ms(stt_final_ms=stt_final_ms, vad_speech_ratio=vad_ratio),
    )


def budget_from_stream_metrics(stream_metrics: Any) -> LatencyBudget:
    if stream_metrics is None:
        return LatencyBudget()
    return LatencyBudget(
        llm_ttft_ms=_positive_int(getattr(stream_metrics, "llm_first_token_ms", None)),
        tts_ttfa_ms=_positive_int(getattr(stream_metrics, "tts_first_byte_ms", None)),
        crm_execute_ms=_positive_int(getattr(stream_metrics, "crm_execute_ms", None)),
    )


def compute_e2r_ms(
    *,
    stt_final_ms: int | None,
    llm_ttft_ms: int | None,
    tts_ttfa_ms: int | None,
    wall_ms: int | None = None,
) -> int | None:
    if wall_ms is not None and wall_ms >= 0:
        return int(wall_ms)
    parts = [stt_final_ms, llm_ttft_ms, tts_ttfa_ms]
    if any(part is None for part in parts):
        return None
    return int(sum(int(part) for part in parts))


def merge_budget(
    gateway: LatencyBudget | None,
    stream: LatencyBudget | None,
    *,
    sip_ms: int | None = None,
    wall_ms: int | None = None,
) -> LatencyBudget:
    gw = gateway or LatencyBudget()
    st = stream or LatencyBudget()
    merged = LatencyBudget(
        sip_ms=sip_ms if sip_ms is not None else gw.sip_ms,
        vad_ms=gw.vad_ms,
        stt_final_ms=gw.stt_final_ms,
        llm_ttft_ms=st.llm_ttft_ms,
        tts_ttfa_ms=st.tts_ttfa_ms,
        crm_execute_ms=st.crm_execute_ms,
    )
    merged.e2r_ms = compute_e2r_ms(
        stt_final_ms=merged.stt_final_ms,
        llm_ttft_ms=merged.llm_ttft_ms,
        tts_ttfa_ms=merged.tts_ttfa_ms,
        wall_ms=wall_ms,
    )
    return merged


def apply_budget_to_call_metadata(meta: dict[str, Any], budget: LatencyBudget) -> dict[str, Any]:
    payload = budget.to_dict()
    if not payload:
        return meta
    out = dict(meta)
    out[LATENCY_BUDGET_META_KEY] = payload
    history = out.get(LATENCY_BUDGET_HISTORY_KEY)
    if not isinstance(history, list):
        history = []
    history = list(history)
    history.append(payload)
    out[LATENCY_BUDGET_HISTORY_KEY] = history[-50:]
    return out


def budget_table_for_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    current = meta.get(LATENCY_BUDGET_META_KEY)
    if isinstance(current, dict):
        return dict(current)
    return {}


def rollup_from_budget(budget: LatencyBudget, rollup: LatencyBudgetRollup) -> None:
    data = budget.to_dict()
    if not data:
        return
    rollup.samples += 1
    for key in ("sip_ms", "vad_ms", "stt_final_ms", "llm_ttft_ms", "tts_ttfa_ms", "crm_execute_ms", "e2r_ms"):
        value = data.get(key)
        if value is None:
            continue
        getattr(rollup, key).append(float(value))
