/**
 * Voximplant WebSocket media JSON (call.sendMediaTo ↔ gateway).
 * @see https://voximplant.com/docs/guides/media-streams/websocket
 */

export interface VoxMediaMessage {
  event: 'media';
  sequenceNumber: number;
  media: { chunk: number; timestamp: number; payload: string };
}

/** Per-session sequence counter for Voximplant media messages. */
class VoxSequenceCounter {
  private seq = 0;
  private chunk = 0;

  nextSeq(): number {
    return this.seq++;
  }

  nextChunk(): number {
    return this.chunk++;
  }

  reset(): void {
    this.seq = 0;
    this.chunk = 0;
  }
}

/** Map to track sequence counters per WebSocket connection. */
const wsSequenceCounters = new WeakMap<object, VoxSequenceCounter>();

function getCounter(ws: unknown): VoxSequenceCounter {
  let counter = wsSequenceCounters.get(ws as object);
  if (!counter) {
    counter = new VoxSequenceCounter();
    wsSequenceCounters.set(ws as object, counter);
  }
  return counter;
}

/** Voximplant may send start/stop before media frames — ignore without error. */
const VOX_IGNORED_EVENTS = new Set(['start', 'stop', 'connected', 'playback_started', 'playback_finished']);

export function parseVoxMediaMessage(text: string): Buffer | null | 'ignore' {
  try {
    const data = JSON.parse(text) as { event?: string; media?: { payload?: string } };
    const event = String(data.event || '').trim().toLowerCase();
    if (!event) return null;
    if (VOX_IGNORED_EVENTS.has(event)) return 'ignore';
    if (event !== 'media' || !data.media?.payload) return null;
    return Buffer.from(data.media.payload, 'base64');
  } catch {
    return null;
  }
}

export function buildVoxStartMessage(ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  if (ws) {
    counter.reset();
  }
  return JSON.stringify({
    event: 'start',
    sequenceNumber: counter.nextSeq(),
    start: {
      mediaFormat: {
        // Downlink media is sent as G.711 μ-law bytes.
        encoding: 'audio/x-mulaw',
        sampleRate: 8000,
        channels: 1,
      },
    },
  });
}

export function buildVoxMediaMessage(payload: Buffer, ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  const timestamp = Date.now();
  return JSON.stringify({
    event: 'media',
    sequenceNumber: counter.nextSeq(),
    media: {
      chunk: counter.nextChunk(),
      timestamp,
      payload: payload.toString('base64'),
    },
  });
}

export function buildVoxStopMessage(ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  return JSON.stringify({
    event: 'stop',
    sequenceNumber: counter.nextSeq(),
  });
}
