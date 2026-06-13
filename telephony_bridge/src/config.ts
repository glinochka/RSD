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
  backendRequestTimeoutMs: Math.max(
    1000,
    Number.parseInt(process.env.TELEPHONY_BACKEND_REQUEST_TIMEOUT_MS || '15000', 10),
  ),
  /** Signal webhooks only (inbound / answered / hangup). Default true for streaming PSTN. */
  controlOnlyMode:
    (process.env.TELEPHONY_BRIDGE_CONTROL_ONLY || 'true').trim().toLowerCase() !== 'false',
};
