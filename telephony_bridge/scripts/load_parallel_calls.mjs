/**
 * Load smoke test: parallel WS media sessions (stage 9).
 * Replaces legacy webhook recording_ready → /turn path.
 *
 * Usage:
 *   TELEPHONY_MEDIA_WS_URL=ws://127.0.0.1:8200/ws node scripts/load_parallel_calls.mjs
 */
import WebSocket from 'ws';

const WS_URL = (process.env.TELEPHONY_MEDIA_WS_URL || 'ws://127.0.0.1:8200/ws').replace(/\/$/, '');
const PARALLEL = Number.parseInt(process.env.TELEPHONY_LOAD_PARALLEL || '3', 10);
const FRAME_BYTES = 160;
const FRAME_MS = 20;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function noiseUlaw(bytes) {
  const buf = Buffer.alloc(bytes);
  for (let i = 0; i < bytes; i += 1) {
    buf[i] = i % 2 === 0 ? 0x00 : 0xff;
  }
  return buf;
}

async function runSession(index) {
  const callId = `load-ws-${Date.now()}-${index}`;
  const partials = [];
  const finals = [];

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(WS_URL);
    const timer = setTimeout(() => reject(new Error(`timeout session ${index}`)), 25000);

    ws.on('open', () => {
      ws.send(
        JSON.stringify({
          type: 'session.start',
          payload: {
            call_id: callId,
            connection_id: 1,
            caller_e164: `+7900123400${index}`,
            codec: 'pcmu',
          },
        }),
      );
    });

    ws.on('message', (data, isBinary) => {
      if (isBinary) return;
      try {
        const msg = JSON.parse(String(data));
        if (msg.type === 'stt.partial') partials.push(msg);
        if (msg.type === 'stt.final') finals.push(msg);
        if (msg.type === 'session.start' && msg.payload?.ok) {
          void pumpAudio();
        }
      } catch {
        // ignore
      }
    });

    async function pumpAudio() {
      for (let i = 0; i < 40; i += 1) {
        const payload = noiseUlaw(FRAME_BYTES);
        const frame = Buffer.allocUnsafe(1 + payload.length);
        frame[0] = 0x01;
        payload.copy(frame, 1);
        ws.send(frame);
        await sleep(FRAME_MS);
      }
      await sleep(1200);
      ws.send(JSON.stringify({ type: 'session.end', payload: { reason: 'load_test' } }));
      clearTimeout(timer);
      ws.close();
      resolve({ index, callId, partials: partials.length, finals: finals.length });
    }

    ws.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

const results = await Promise.all(
  Array.from({ length: Math.max(1, PARALLEL) }, (_, i) =>
    runSession(i).catch((err) => ({ index: i, error: String(err) })),
  ),
);
const failed = results.filter((r) => r.error || (r.finals ?? 0) < 1);
console.log(JSON.stringify({ ok: failed.length === 0, ws_url: WS_URL, results }, null, 2));
process.exit(failed.length === 0 ? 0 : 1);
