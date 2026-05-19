import express, { NextFunction, Request, Response } from 'express';

import { fetchWebhookAuth, telephonyCallEvent, telephonyResolve } from './backend_client';
import {
  buildListenAfterGreetingActions,
  transferOperatorAction,
} from './dialog/actions';
import { handlePartialTranscript } from './dialog/partial_transcript';
import { handleDtmfDigit } from './dialog/dtmf';
import { handleUserRecordingTurn } from './dialog/recording_turn';
import {
  backendUnavailableActions,
  cpaasTimeoutActions,
  isBackendUnavailableError,
} from './resilience';
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
  res.json({ ok: true, service: 'telephony_bridge' });
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

  let secret: string;
  try {
    secret = await getWebhookSecret(connectionId);
  } catch (err) {
    if (isBackendUnavailableError(err)) {
      res.status(200).json({ ok: true, actions: backendUnavailableActions(), degraded: true });
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

  if (envelope.event === 'call.partial_transcript') {
    let partialActions: Array<Record<string, unknown>> = [];
    try {
      partialActions = await handlePartialTranscript(session, envelope, callerE164);
      await sessionStore.set(session);
    } catch (err) {
      console.error('partial transcript failed', err instanceof Error ? err.message : err);
    }
    res.status(200).json({ ok: true, actions: partialActions, partial: true });
    return;
  }

  try {
    session.transition(initialStateForEvent(envelope.event));
  } catch {
    // Non-fatal state mismatch
  }
  await sessionStore.set(session);

  let hangupStatus: string | undefined;
  if (envelope.event === 'call.hangup') {
    const reason = String(envelope.payload.reason || 'completed').toLowerCase();
    if (reason === 'transferred') {
      hangupStatus = 'transferred';
    } else if (reason === 'failed' || reason === 'timeout' || reason === 'no_answer') {
      hangupStatus = 'failed';
    } else {
      hangupStatus = 'completed';
    }
  }

  const statusMap: Record<string, string | undefined> = {
    'call.inbound': 'ringing',
    'call.answered': 'active',
    'call.recording_ready': 'active',
    'call.hangup': hangupStatus,
  };

  let callEvent: { call_db_id: number; status: string; created: boolean } | null = null;
  try {
    if (envelope.event === 'call.inbound') {
      recordCallStarted();
    }
    callEvent = await telephonyCallEvent({
      connection_id: connectionId,
      external_call_id: envelope.call_id,
      caller_e164: callerE164,
      event: envelope.event,
      status: statusMap[envelope.event],
      recording_url: envelope.payload.recording_url ? String(envelope.payload.recording_url) : undefined,
      duration_sec:
        envelope.payload.duration_sec !== undefined
          ? Number(envelope.payload.duration_sec)
          : undefined,
      metadata: {
        event_id: envelope.event_id,
        emitted_at: envelope.emitted_at,
        bridge_state: session.state,
        dtmf: envelope.event === 'dtmf' ? envelope.payload.digit : undefined,
        leg: envelope.event === 'call.recording_ready' ? envelope.payload.leg : undefined,
        turn_index: envelope.payload.turn_index,
      },
    });
    session.callDbId = callEvent.call_db_id;
    await sessionStore.set(session);
  } catch (err) {
    console.error('call-event failed', err instanceof Error ? err.message : err);
    if (isBackendUnavailableError(err)) {
      res.status(200).json({ ok: true, actions: backendUnavailableActions(), degraded: true });
      return;
    }
    res.status(502).json({ ok: false, detail: 'Backend call-event failed' });
    return;
  }

  if (envelope.event === 'call.inbound' || envelope.event === 'call.answered') {
    try {
      const resolved = await telephonyResolve({
        connection_id: connectionId,
        caller_e164: callerE164,
        call_id: envelope.call_id,
      });
      session.resolved = {
        welcome_message: resolved.welcome_message as string | null | undefined,
        voice_id: resolved.voice_id as string | undefined,
        record_calls: Boolean(resolved.record_calls),
        disclaimer_played: Boolean(resolved.disclaimer_played),
        operator_transfer_e164: resolved.operator_transfer_e164 as string | undefined,
      };
      await sessionStore.set(session);
    } catch (err) {
      console.error('resolve failed', err instanceof Error ? err.message : err);
      if (isBackendUnavailableError(err) && envelope.event === 'call.answered') {
        res.status(200).json({ ok: true, actions: backendUnavailableActions(), degraded: true });
        return;
      }
    }
  }

  if (envelope.event === 'call.answered') {
    session.markAnswered();
    await sessionStore.set(session);
  }

  if (envelope.event === 'call.hangup') {
    recordCallCompleted(hangupStatus === 'transferred');
    session.transition('END');
    await sessionStore.delete(envelope.call_id, connectionId);
  }

  const actions: Array<Record<string, unknown>> = [];

  if (envelope.event === 'call.inbound') {
    actions.push({ type: 'answer' });
  }

  if (envelope.event === 'call.answered') {
    actions.push(...buildListenAfterGreetingActions(session));
    try {
      session.transition('LISTENING');
    } catch {
      // ignore
    }
    await sessionStore.set(session);
  }

  if (envelope.event === 'call.recording_ready') {
    try {
      session.transition('PROCESSING');
    } catch {
      // ignore
    }
    try {
      const turnActions = await handleUserRecordingTurn(session, envelope, callerE164);
      actions.push(...turnActions);
      if (turnActions.some((a) => a.type === 'play_tts')) {
        try {
          session.transition('SPEAKING');
        } catch {
          // ignore
        }
      }
      await sessionStore.set(session);
    } catch (err) {
      console.error('recording turn failed', err instanceof Error ? err.message : err);
      if (isBackendUnavailableError(err)) {
        actions.push(...backendUnavailableActions());
      } else {
        res.status(502).json({ ok: false, detail: 'Turn processing failed' });
        return;
      }
    }
  }

  if (envelope.event === 'dtmf') {
    try {
      const dtmfActions = await handleDtmfDigit(
        session,
        String(envelope.payload.digit || ''),
        callerE164,
      );
      actions.push(...dtmfActions);
      await sessionStore.set(session);
    } catch (err) {
      console.error('dtmf failed', err instanceof Error ? err.message : err);
      if (String(envelope.payload.digit || '') === '0') {
        actions.push(transferOperatorAction(session));
      }
    }
  }

  if (String(envelope.payload.provider_timeout || '') === 'true') {
    actions.push(...cpaasTimeoutActions());
  }

  res.status(200).json({ ok: true, actions, call_db_id: callEvent?.call_db_id });
});

app.get('/internal/sessions', requireBridgeApiKey, (_req, res) => {
  res.json({ ok: true, store: config.sessionStore });
});

app.listen(config.port, () => {
  console.log(`telephony_bridge listening on ${config.port}`);
});
