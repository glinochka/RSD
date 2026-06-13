#!/usr/bin/env node
/**
 * Stage 3 smoke test: mock STT + energy VAD, synthetic μ-law speech-like noise.
 * Usage: STT_PROVIDER=mock TELEPHONY_MEDIA_PIPELINE_ENABLED=true node scripts/test_pipeline.mjs
 */
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import WebSocket from 'ws';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..');
const port = 18200;
const wsUrl = `ws://127.0.0.1:${port}/ws`;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function makeNoiseUlaw(bytes) {
  const buf = Buffer.alloc(bytes);
  for (let i = 0; i < bytes; i += 1) {
    buf[i] = i % 2 === 0 ? 0x00 : 0xff;
  }
  return buf;
}

async function main() {
  const child = spawn('npm', ['start'], {
    cwd: root,
    shell: true,
    env: {
      ...process.env,
      PORT: String(port),
      STT_PROVIDER: 'mock',
      TELEPHONY_MEDIA_PIPELINE_ENABLED: 'true',
      TELEPHONY_MEDIA_LOG_LEVEL: 'info',
      TELEPHONY_MEDIA_LOOPBACK_TRANSPORT: 'binary',
      VAD_ENERGY_THRESHOLD: '0.005',
      TURN_SILENCE_MS: '400',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  for (let i = 0; i < 30; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`);
      if (res.ok) break;
    } catch {
      // retry
    }
    await sleep(500);
  }

  const partials = [];
  const finals = [];

  await new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const timer = setTimeout(() => reject(new Error('timeout')), 20000);

    ws.on('open', () => {
      ws.send(
        JSON.stringify({
          type: 'session.start',
          payload: {
            call_id: 'test-pipeline-1',
            connection_id: 1,
            caller_e164: '+79000000001',
            codec: 'pcmu',
          },
        }),
      );
    });

    ws.on('message', (data, isBinary) => {
      if (isBinary) return;
      const text = String(data);
      try {
        const msg = JSON.parse(text);
        if (msg.type === 'session.start' && msg.payload?.ok) {
          sendFrames();
        }
        if (msg.type === 'stt.partial') partials.push(msg.payload?.text);
        if (msg.type === 'stt.final') {
          finals.push(msg.payload?.text);
          clearTimeout(timer);
          ws.send(JSON.stringify({ type: 'session.end' }));
          ws.close();
        }
      } catch {
        // binary
      }
    });

    ws.on('error', reject);

    ws.on('close', () => {
      clearTimeout(timer);
      resolve();
    });

    const sendFrame = (payload, delayMs) => {
      setTimeout(() => {
        const frame = Buffer.allocUnsafe(1 + payload.length);
        frame[0] = 0x01;
        payload.copy(frame, 1);
        if (ws.readyState === WebSocket.OPEN) ws.send(frame);
      }, delayMs);
    };

    const sendFrames = () => {
      for (let i = 0; i < 80; i += 1) {
        sendFrame(makeNoiseUlaw(160), i * 20);
      }
      const silence = Buffer.alloc(160, 0xff);
      for (let j = 0; j < 40; j += 1) {
        sendFrame(silence, 80 * 20 + j * 20);
      }
    };
  });

  child.kill();
  console.log('partials:', partials.length, partials.slice(0, 3));
  console.log('finals:', finals);
  if (partials.length < 1 || finals.length < 1) {
    process.exit(1);
  }
  console.log('OK pipeline smoke test');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
