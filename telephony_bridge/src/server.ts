import express, { NextFunction, Request, Response } from 'express';

import { fetchWebhookAuth } from './backend_client';
import { handleSignalWebhook, isSignalEvent } from './control_webhook';
import { backendUnavailableControlHints, isBackendUnavailableError } from './resilience';
import { checkRateLimit } from './security/rate_limit';
import { verifyWebhookSignature } from './security/verify_signature';
import { CallSession, initialStateForEvent } from './session/call_session';
import { createSessionStore } from './session/store';
import { config } from './config';
import { metricsSnapshot, recordCallCompleted, recordCallStarted } from './metrics';
import { voximplantProvider } from './providers/voximplant';
import type { WebhookEnvelope } from './providers/types';

const app = express();
const sessionStore = createSessionStore(config.sessionStore, config.redisUrl);
const secretCache = new Map<number, { secret: string; expiresAt: number }>();
const dedupKeys = new Map<string, number>();
const DEDUP_MAX = 5000;
const DEDUP_TTL_MS = 24 * 60 * 60 * 1000;

const LEGACY_EVENTS = new Set([
  'call.recording_ready',
  'call.partial_transcript',
  'dtmf',
]);

app.use(
  express.json({
    verify: (req, _res, buf) => {
      (req as Request & { rawBody?: Buffer }).rawBody = buf;
    },
  }),
);

function requireBridgeApiKey(req: Request, res: Response, next: NextFunction): void {
  const key = (req.header('X-API-Key') || req.header('X-Telephony-Bridge-API-Key') || '').trim();
  if (!key || key !== config.bridgeApiKey) {
    res.status(401).json({ detail: 'Invalid bridge API key' });
    return;
  }
  next();
}

function clientIp(req: Request): string {
  const forwarded = (req.header('x-forwarded-for') || '').split(',')[0]?.trim();
  if (forwarded) return forwarded;
  const realIp = (req.header('x-real-ip') || '').trim();
  if (realIp) return realIp;
  return req.socket.remoteAddress || 'unknown';
}

function checkWebhookRateLimit(req: Request, res: Response, connectionId: number): boolean {
  const ip = clientIp(req);
  const perConn = checkRateLimit({
    key: `conn:${connectionId}`,
    maxRequests: config.webhookRateLimitPerConnection,
    windowSeconds: config.webhookRateWindowSeconds,
  });
  if (!perConn.allowed) {
    res.status(429).json({ ok: false, detail: 'Rate limit exceeded (connection)' });
    res.setHeader('Retry-After', String(perConn.retryAfterSeconds));
    return false;
  }
  const perIp = checkRateLimit({
    key: `ip:${ip}`,
    maxRequests: config.webhookRateLimitPerIp,
    windowSeconds: config.webhookRateWindowSeconds,
  });
  if (!perIp.allowed) {
    res.status(429).json({ ok: false, detail: 'Rate limit exceeded (ip)' });
    res.setHeader('Retry-After', String(perIp.retryAfterSeconds));
    return false;
  }
  return true;
}

async function getWebhookSecret(connectionId: number): Promise<string> {
  const cached = secretCache.get(connectionId);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.secret;
  }
  const auth = await fetchWebhookAuth(connectionId);
  if (!auth.is_active) {
    throw new Error('Telephony channel inactive');
  }
  secretCache.set(connectionId, {
    secret: auth.webhook_secret,
    expiresAt: Date.now() + 5 * 60 * 1000,
  });
  return auth.webhook_secret;
}

function pruneDedup(): void {
  const now = Date.now();
  for (const [key, ts] of dedupKeys.entries()) {
    if (now - ts > DEDUP_TTL_MS) dedupKeys.delete(key);
  }
}

function isDuplicate(envelope: WebhookEnvelope): boolean {
  const key = `${envelope.connection_id}:${envelope.call_id}:${envelope.event}:${envelope.event_id}`;
  if (dedupKeys.has(key)) {
    return true;
  }
  dedupKeys.set(key, Date.now());
  pruneDedup();
  if (dedupKeys.size > DEDUP_MAX) {
    const oldest = dedupKeys.keys().next().value;
    if (oldest) dedupKeys.delete(oldest);
  }
  return false;
}

function callerFromPayload(payload: Record<string, unknown>): string {
  const raw = String(payload.caller_e164 || payload.from || '+00000000000').trim();
  return raw || '+00000000000';
}

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'telephony_bridge',
    control_only: true,
  });
});

app.get('/metrics', requireBridgeApiKey, (_req, res) => {
  res.json({ ok: true, ...metricsSnapshot(config.turnLatencyAlertP95Ms) });
});

app.post('/webhook/voximplant/:connectionId', async (req, res) => {
  const connectionId = Number.parseInt(String(req.params.connectionId), 10);
  if (!Number.isFinite(connectionId) || connectionId <= 0) {
    res.status(400).json({ ok: false, detail: 'Invalid connection_id' });
    return;
  }

  if (!checkWebhookRateLimit(req, res, connectionId)) {
    return;
  }

  const rawBody = (req as Request & { rawBody?: Buffer }).rawBody;
  if (!rawBody) {
    res.status(400).json({ ok: false, detail: 'Missing body' });
    return;
  }

  const timestamp = (req.header('X-RSD-Telephony-Timestamp') || '').trim();
  const signature = (req.header('X-RSD-Telephony-Signature') || '').trim();
  if (!timestamp || !signature) {
    res.status(401).json({ ok: false, detail: 'Signature headers required' });
    return;
  }

  let envelope: WebhookEnvelope;
  try {
    envelope = voximplantProvider.parseWebhookBody(req.body, connectionId);
  } catch (err) {
    res.status(400).json({ ok: false, detail: String(err) });
    return;
  }

  if (LEGACY_EVENTS.has(envelope.event)) {
    res.status(410).json({
      ok: false,
      detail: 'Legacy PSTN media path removed; use telephony_media_gateway + orchestrator',
      event: envelope.event,
    });
    return;
  }

  if (!isSignalEvent(envelope.event)) {
    res.status(400).json({ ok: false, detail: `Unsupported event: ${envelope.event}` });
    return;
  }

  let secret: string;
  try {
    secret = await getWebhookSecret(connectionId);
  } catch (err) {
    if (isBackendUnavailableError(err)) {
      res.status(200).json({ ok: true, actions: [], ...backendUnavailableControlHints() });
      return;
    }
    res.status(404).json({ ok: false, detail: String(err) });
    return;
  }

  const valid = verifyWebhookSignature({
    secret,
    timestamp,
    connectionId,
    rawBody,
    signatureHex: signature,
    ttlSeconds: config.webhookSignatureTtlSeconds,
  });
  if (!valid) {
    res.status(401).json({ ok: false, detail: 'Invalid signature' });
    return;
  }

  if (isDuplicate(envelope)) {
    res.status(200).json({ ok: true, actions: [], duplicate: true });
    return;
  }

  const callerE164 = callerFromPayload(envelope.payload);
  let session =
    (await sessionStore.get(envelope.call_id, connectionId, callerE164)) ||
    new CallSession(envelope.call_id, connectionId, callerE164);

  try {
    session.transition(initialStateForEvent(envelope.event));
  } catch {
    // Non-fatal state mismatch
  }

  try {
    const result = await handleSignalWebhook({
      envelope,
      session,
      callerE164,
      connectionId,
      onInbound: () => recordCallStarted(),
      onHangup: (status) => {
        recordCallCompleted(status === 'transferred');
        session.transition('END');
      },
    });
    if (envelope.event === 'call.hangup') {
      await sessionStore.delete(envelope.call_id, connectionId);
    } else {
      await sessionStore.set(session);
    }
      res.status(200).json({
        ok: true,
        actions: result.actions,
        call_db_id: result.callEvent?.call_db_id,
        control_only: true,
        operator_transfer_e164: session.resolved?.operator_transfer_e164,
        record_calls: Boolean(session.resolved?.record_calls),
        disclaimer_played: Boolean(session.resolved?.disclaimer_played),
        ...(result.degraded
          ? { degraded: true, transfer_e164: result.transfer_e164 || 'operator' }
          : {}),
      });
  } catch (err) {
    console.error('control webhook failed', err instanceof Error ? err.message : err);
    if (isBackendUnavailableError(err)) {
      res.status(200).json({
        ok: true,
        actions: [],
        ...backendUnavailableControlHints(session.resolved?.operator_transfer_e164),
      });
      return;
    }
    res.status(502).json({ ok: false, detail: 'Backend call-event failed' });
  }
});

app.get('/internal/sessions', requireBridgeApiKey, (_req, res) => {
  res.json({ ok: true, store: config.sessionStore });
});

app.listen(config.port, () => {
  console.log(`telephony_bridge listening on ${config.port} (control-only)`);
});
