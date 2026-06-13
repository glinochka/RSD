from app.telephony import metrics as telephony_metrics


def test_metrics_snapshot_and_alert():
    telephony_metrics.reset_for_tests()
    telephony_metrics.record_call_started()
    telephony_metrics.record_call_started()
    telephony_metrics.record_call_completed(transferred=True)
    telephony_metrics.record_stt_empty()
    for ms in range(1, 21):
        telephony_metrics.record_turn_latency_ms(ms * 500)

    snap = telephony_metrics.snapshot(alert_p95_ms=5000)
    assert snap["calls_started"] == 2
    assert snap["calls_completed"] == 1
    assert snap["transfer_rate"] == 1.0
    assert snap["turn_latency_p95_ms"] is not None
    assert snap["turn_latency_p95_ms"] > 5000
    assert snap["alerts"]
