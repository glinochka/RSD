#!/usr/bin/env node
/**
 * Optional latency simulator: replay recorded WS JSONL trace against media gateway.
 *
 * Trace format (one JSON object per line):
 *   {"delay_ms":20,"type":"binary","payload_b64":"..."}
 *   {"delay_ms":0,"type":"control","body":{"type":"session.start","payload":{...}}}
 *
 * Usage:
 *   node scripts/replay_ws_trace.mjs traces/sample.jsonl
 */
import fs from 'fs';
import path from 'path';
import WebSocket from 'ws';

const tracePath = process.argv[2];
if (!tracePath) {
  console.error('Usage: node scripts/replay_ws_trace.mjs <trace.jsonl>');
  process.exit(2);
}

const WS_URL = (process.env.TELEPHONY_MEDIA_WS_URL || 'ws://127.0.0.1:8200/ws').replace(/\/$/, '');
const lines = fs
  .readFileSync(path.resolve(tracePath), 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter(Boolean);

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

await new Promise((resolve, reject) => {
  const ws = new WebSocket(WS_URL);
  const timer = setTimeout(() => reject(new Error('replay timeout')), 120000);

  ws.on('open', async () => {
    try {
      for (const line of lines) {
        const row = JSON.parse(line);
        await sleep(Number(row.delay_ms) || 0);
        if (row.type === 'binary' && row.payload_b64) {
          ws.send(Buffer.from(row.payload_b64, 'base64'));
        } else if (row.type === 'control' && row.body) {
          ws.send(JSON.stringify(row.body));
        }
      }
      await sleep(500);
      ws.send(JSON.stringify({ type: 'session.end', payload: { reason: 'replay' } }));
      clearTimeout(timer);
      resolve(null);
    } catch (err) {
      clearTimeout(timer);
      reject(err);
    }
  });

  ws.on('error', reject);
});

console.log(JSON.stringify({ ok: true, events: lines.length, ws_url: WS_URL }));
process.exit(0);
