const required = (name: string, value: string | undefined): string => {
  const v = (value || '').trim();
  if (!v) {
    throw new Error(`${name} must be set`);
  }
  return v;
};

export const config = {
  port: Number.parseInt(process.env.PORT || '8100', 10),
  bridgeApiKey: required('TELEPHONY_BRIDGE_API_KEY', process.env.TELEPHONY_BRIDGE_API_KEY),
  backendUrl: required('TELEPHONY_BACKEND_URL', process.env.TELEPHONY_BACKEND_URL).replace(/\/$/, ''),
  backendInternalKey: required(
    'TELEPHONY_BACKEND_INTERNAL_KEY',
    process.env.TELEPHONY_BACKEND_INTERNAL_KEY,
  ),
  signingSecret: (
    process.env.TELEPHONY_BACKEND_SIGNING_SECRET ||
    process.env.TELEPHONY_BACKEND_INTERNAL_KEY ||
    ''
  ).trim(),
  webhookSignatureTtlSeconds: Math.max(
    30,
    Number.parseInt(process.env.TELEPHONY_WEBHOOK_SIGNATURE_TTL_SECONDS || '300', 10),
  ),
  sessionStore: (process.env.TELEPHONY_SESSION_STORE || 'memory').trim().toLowerCase(),
  redisUrl: (process.env.REDIS_URL || '').trim(),
  endpointSilenceMs: Math.max(
    400,
    Math.min(700, Number.parseInt(process.env.TELEPHONY_ENDPOINT_SILENCE_MS || '600', 10)),
  ),
  streamingEnabled: (process.env.TELEPHONY_STREAMING_ENABLED || 'true').trim().toLowerCase() !== 'false',
  bargeInEnabled: (process.env.TELEPHONY_BARGE_IN_ENABLED || 'true').trim().toLowerCase() !== 'false',
  backchannelMinMs: Math.max(
    3000,
    Number.parseInt(process.env.TELEPHONY_BACKCHANNEL_MIN_MS || '5000', 10),
  ),
  ssmlEnabled: (process.env.TELEPHONY_SSML_ENABLED || 'true').trim().toLowerCase() !== 'false',
  crmFillerThresholdMs: Math.max(
    500,
    Number.parseInt(process.env.TELEPHONY_CRM_FILLER_THRESHOLD_MS || '1500', 10),
  ),
  webhookRateLimitPerConnection: Math.max(
    1,
    Number.parseInt(process.env.TELEPHONY_WEBHOOK_RATE_LIMIT_PER_CONNECTION || '120', 10),
  ),
  webhookRateLimitPerIp: Math.max(
    1,
    Number.parseInt(process.env.TELEPHONY_WEBHOOK_RATE_LIMIT_PER_IP || '240', 10),
  ),
  webhookRateWindowSeconds: Math.max(
    1,
    Number.parseInt(process.env.TELEPHONY_WEBHOOK_RATE_WINDOW_SECONDS || '60', 10),
  ),
  turnLatencyAlertP95Ms: Math.max(
    1000,
    Number.parseInt(process.env.TELEPHONY_TURN_LATENCY_ALERT_P95_MS || '10000', 10),
  ),
  backendRequestTimeoutMs: Math.max(
    1000,
    Number.parseInt(process.env.TELEPHONY_BACKEND_REQUEST_TIMEOUT_MS || '15000', 10),
  ),
  maxTurns: Math.max(1, Number.parseInt(process.env.TELEPHONY_MAX_TURNS || '15', 10)),
  maxCallMinutes: Math.max(1, Number.parseInt(process.env.TELEPHONY_MAX_CALL_MINUTES || '15', 10)),
  recordMaxSec: Math.max(
    5,
    Number.parseInt(process.env.TELEPHONY_MAX_TURN_SECONDS || '30', 10),
  ),
  recordSilenceSec: Math.max(
    0.4,
    Number.parseInt(process.env.TELEPHONY_RECORD_SILENCE_SEC || '0', 10) ||
      0,
  ),
};

/** Endpointing silence for Voximplant `record` action (stage 5: 400–700 ms). */
export function recordSilenceSecFromConfig(): number {
  const fromMs = config.endpointSilenceMs / 1000;
  if (config.recordSilenceSec > 0) {
    return config.recordSilenceSec;
  }
  return Math.max(0.4, Math.min(0.7, fromMs));
}
