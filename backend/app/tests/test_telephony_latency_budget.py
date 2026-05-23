from app.telephony.latency_budget import (
    LatencyBudget,
    apply_budget_to_call_metadata,
    budget_from_gateway,
    compute_e2r_ms,
    merge_budget,
)
from app.telephony import metrics as telephony_metrics


def test_budget_from_gateway_metrics():
    budget = budget_from_gateway(
        {"metrics": {"stt_final_ms": 420, "vad_speech_ratio": 0.6}},
    )
    assert budget.stt_final_ms == 420
    assert budget.vad_ms == 168


def test_merge_budget_e2r_wall():
    merged = merge_budget(
        budget_from_gateway({"metrics": {"stt_final_ms": 400, "vad_speech_ratio": 0.5}}),
        LatencyBudget(llm_ttft_ms=180, tts_ttfa_ms=90),
        wall_ms=750,
    )
    assert merged.e2r_ms == 750
    assert merged.llm_ttft_ms == 180


def test_compute_e2r_sum():
    assert compute_e2r_ms(stt_final_ms=400, llm_ttft_ms=200, tts_ttfa_ms=100) == 700


def test_apply_budget_to_metadata_history():
    meta = apply_budget_to_call_metadata({}, LatencyBudget(stt_final_ms=300, e2r_ms=650))
    assert meta["latency_budget"]["stt_final_ms"] == 300
    assert len(meta["latency_budget_turns"]) == 1


def test_metrics_record_latency_budget():
    telephony_metrics.reset_for_tests()
    telephony_metrics.record_latency_budget(LatencyBudget(e2r_ms=700, llm_ttft_ms=200))
    snap = telephony_metrics.snapshot(alert_p95_ms=10000, alert_e2r_p90_ms=850)
    assert snap["latency_budget_samples"] == 1
    assert snap["latency_budget_p90"]["e2r_p90_ms"] == 700.0
