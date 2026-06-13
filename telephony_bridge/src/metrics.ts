type MetricsState = {
  calls_started: number;
  calls_completed: number;
  transfers: number;
  stt_empty: number;
  turn_latencies_ms: number[];
};

const state: MetricsState = {
  calls_started: 0,
  calls_completed: 0,
  transfers: 0,
  stt_empty: 0,
  turn_latencies_ms: [],
};

const MAX_LATENCY_SAMPLES = 500;

function percentile(values: number[], pct: number): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  const idx = Math.min(ordered.length - 1, Math.max(0, Math.round((pct / 100) * (ordered.length - 1))));
  return ordered[idx];
}

export function recordCallStarted(): void {
  state.calls_started += 1;
}

export function recordCallCompleted(transferred = false): void {
  state.calls_completed += 1;
  if (transferred) state.transfers += 1;
}

export function recordSttEmpty(): void {
  state.stt_empty += 1;
}

export function recordTurnLatencyMs(ms: number): void {
  if (ms < 0) return;
  state.turn_latencies_ms.push(ms);
  if (state.turn_latencies_ms.length > MAX_LATENCY_SAMPLES) {
    state.turn_latencies_ms.shift();
  }
}

export function metricsSnapshot(alertP95Ms: number): Record<string, unknown> {
  const p95 = percentile(state.turn_latencies_ms, 95);
  const completed = state.calls_completed;
  const transferRate = completed > 0 ? state.transfers / completed : 0;
  const sttEmptyRate =
    state.turn_latencies_ms.length > 0 ? state.stt_empty / state.turn_latencies_ms.length : 0;

  const alerts: Array<Record<string, string>> = [];
  if (p95 !== null && p95 > alertP95Ms) {
    alerts.push({
      code: 'turn_latency_p95_high',
      message: `turn_latency_p95 ${p95.toFixed(0)}ms exceeds threshold ${alertP95Ms}ms`,
      severity: 'warning',
    });
  }

  return {
    calls_started: state.calls_started,
    calls_completed: state.calls_completed,
    turn_latency_p95_ms: p95 !== null ? Math.round(p95 * 10) / 10 : null,
    transfer_rate: Math.round(transferRate * 10000) / 10000,
    stt_empty_rate: Math.round(sttEmptyRate * 10000) / 10000,
    turn_samples: state.turn_latencies_ms.length,
    alerts,
  };
}
