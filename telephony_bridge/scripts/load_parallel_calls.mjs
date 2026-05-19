/**
 * Load smoke test: 3 parallel signed webhook deliveries (inbound + recording turn).
 * Usage: node scripts/load_parallel_calls.mjs
 */
import crypto from 'crypto';

const BASE = (process.env.TELEPHONY_WEBHOOK_BASE_URL || 'http://127.0.0.1:8100').replace(/\/$/, '');
const CONNECTION_ID = Number.parseInt(process.env.TELEPHONY_TEST_CONNECTION_ID || '1', 10);
const SECRET = process.env.TELEPHONY_TEST_WEBHOOK_SECRET || 'test-secret-32-chars-minimum!!';

function sign(timestamp, connectionId, rawBody) {
  const prefix = Buffer.from(`v1\n${timestamp}\n${connectionId}\n`, 'utf8');
  const message = Buffer.concat([prefix, rawBody]);
  return crypto.createHmac('sha256', SECRET).update(message).digest('hex');
}

async function postWebhook(body) {
  const rawBody = Buffer.from(JSON.stringify(body), 'utf8');
  const timestamp = String(Math.floor(Date.now() / 1000));
  const signature = sign(timestamp, CONNECTION_ID, rawBody);
  const url = `${BASE}/webhook/voximplant/${CONNECTION_ID}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-RSD-Telephony-Timestamp': timestamp,
      'X-RSD-Telephony-Signature': signature,
    },
    body: rawBody,
  });
  const text = await response.text();
  return { status: response.status, text };
}

async function sendCall(index) {
  const callId = `load-call-${index}`;
  const inbound = await postWebhook({
    schema_version: 1,
    event_id: `load-inbound-${Date.now()}-${index}`,
    event: 'call.inbound',
    emitted_at: new Date().toISOString(),
    call_id: callId,
    connection_id: CONNECTION_ID,
    payload: { caller_e164: `+7900123400${index}` },
  });
  const answered = await postWebhook({
    schema_version: 1,
    event_id: `load-answered-${Date.now()}-${index}`,
    event: 'call.answered',
    emitted_at: new Date().toISOString(),
    call_id: callId,
    connection_id: CONNECTION_ID,
    payload: { caller_e164: `+7900123400${index}` },
  });
  const recording = await postWebhook({
    schema_version: 1,
    event_id: `load-recording-${Date.now()}-${index}`,
    event: 'call.recording_ready',
    emitted_at: new Date().toISOString(),
    call_id: callId,
    connection_id: CONNECTION_ID,
    payload: {
      caller_e164: `+7900123400${index}`,
      leg: 'user_turn',
      turn_index: 1,
      user_transcript: 'тестовый вопрос',
    },
  });
  return { index, inbound, answered, recording };
}

const results = await Promise.all([0, 1, 2].map((i) => sendCall(i)));
const failed = results.flatMap((r) => [r.inbound, r.answered, r.recording]).filter((r) => r.status >= 500);
console.log(JSON.stringify({ ok: failed.length === 0, results }, null, 2));
process.exit(failed.length === 0 ? 0 : 1);
