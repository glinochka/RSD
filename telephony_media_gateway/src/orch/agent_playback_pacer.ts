import type { WebSocket } from 'ws';

import { config } from '../config';
import { isDownlinkReady } from './agent_playback_tracker';

const PCM16_FRAME_BYTES = 320;

type Pacer = {
  ws: WebSocket;
  queue: Buffer[];
  timer: ReturnType<typeof setInterval> | null;
  endPending: boolean;
  onDrain: (() => void) | null;
  ready: boolean;
};

const pacers = new Map<string, Pacer>();

function splitPcm16Frames(pcm16: Buffer): Buffer[] {
  if (!pcm16.length) return [];
  const frames: Buffer[] = [];
  for (let i = 0; i < pcm16.length; i += PCM16_FRAME_BYTES) {
    const chunk = pcm16.subarray(i, i + PCM16_FRAME_BYTES);
    if (chunk.length === PCM16_FRAME_BYTES) {
      frames.push(chunk);
      continue;
    }
    if (chunk.length > 0) {
      const padded = Buffer.alloc(PCM16_FRAME_BYTES, 0x00);
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

export function markPlaybackReady(callId: string): void {
  const id = callId.trim();
  const pacer = pacers.get(id);
  if (!pacer) return;
  pacer.ready = true;
}

export function isPlaybackReady(callId: string): boolean {
  const id = callId.trim();
  const pacer = pacers.get(id);
  if (!pacer) return false;
  return pacer.ready;
}

export function enqueuePcm16Playback(
  ws: WebSocket,
  callId: string,
  pcm16: Buffer,
  sendFrame: (ws: WebSocket, frame: Buffer) => void,
): void {
  const id = callId.trim();
  if (!id || !pcm16.length) return;

  const frames = splitPcm16Frames(pcm16);
  if (!frames.length) return;

  let pacer = pacers.get(id);
  if (!pacer) {
    pacer = {
      ws,
      queue: [],
      timer: null,
      endPending: false,
      onDrain: null,
      ready: isDownlinkReady(id),
    };
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
    if (!active.ready) {
      active.queue.unshift(frame);
      return;
    }
    if (active.ws.readyState === active.ws.OPEN) {
      sendFrame(active.ws, frame);
    }
  }, tickMs);
}
