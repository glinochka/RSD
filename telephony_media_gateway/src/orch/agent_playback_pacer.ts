import type { WebSocket } from 'ws';

import { config } from '../config';

const ULAW_FRAME_BYTES = 160;

type Pacer = {
  ws: WebSocket;
  queue: Buffer[];
  timer: ReturnType<typeof setInterval> | null;
  endPending: boolean;
  onDrain: (() => void) | null;
};

const pacers = new Map<string, Pacer>();

function splitUlawFrames(ulaw: Buffer): Buffer[] {
  if (!ulaw.length) return [];
  const frames: Buffer[] = [];
  for (let i = 0; i < ulaw.length; i += ULAW_FRAME_BYTES) {
    const chunk = ulaw.subarray(i, i + ULAW_FRAME_BYTES);
    if (chunk.length === ULAW_FRAME_BYTES) {
      frames.push(chunk);
      continue;
    }
    if (chunk.length > 0) {
      const padded = Buffer.alloc(ULAW_FRAME_BYTES, 0xff);
      chunk.copy(padded);
      frames.push(padded);
    }
  }
  return frames;
}

function finishDrain(pacer: Pacer): void {
  if (!pacer.endPending || !pacer.onDrain) return;
  const cb = pacer.onDrain;
  pacer.endPending = false;
  pacer.onDrain = null;
  cb();
}

export function clearPlaybackPacer(callId: string): void {
  const id = callId.trim();
  const pacer = pacers.get(id);
  if (!pacer) return;
  if (pacer.timer) clearInterval(pacer.timer);
  pacers.delete(id);
}

export function markPlaybackEnd(callId: string, onDrain: () => void): void {
  const id = callId.trim();
  const pacer = pacers.get(id);
  if (!pacer) {
    onDrain();
    return;
  }
  pacer.endPending = true;
  pacer.onDrain = onDrain;
  if (!pacer.queue.length && !pacer.timer) {
    finishDrain(pacer);
  }
}

export function enqueueUlawPlayback(
  ws: WebSocket,
  callId: string,
  ulaw: Buffer,
  sendFrame: (ws: WebSocket, frame: Buffer) => void,
): void {
  const id = callId.trim();
  if (!id || !ulaw.length) return;

  const frames = splitUlawFrames(ulaw);
  if (!frames.length) return;

  let pacer = pacers.get(id);
  if (!pacer) {
    pacer = { ws, queue: [], timer: null, endPending: false, onDrain: null };
    pacers.set(id, pacer);
  }
  pacer.ws = ws;
  pacer.queue.push(...frames);

  if (pacer.timer) return;

  const tickMs = config.audioFrameMs;
  pacer.timer = setInterval(() => {
    const active = pacers.get(id);
    if (!active) return;
    const frame = active.queue.shift();
    if (!frame) {
      if (active.timer) clearInterval(active.timer);
      active.timer = null;
      finishDrain(active);
      return;
    }
    if (active.ws.readyState === active.ws.OPEN) {
      sendFrame(active.ws, frame);
    }
  }, tickMs);
}
