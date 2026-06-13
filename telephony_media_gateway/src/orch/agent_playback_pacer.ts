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

function emitDebugLog(
  hypothesisId: string,
  location: string,
  message: string,
  data: Record<string, unknown>,
): void {
  // #region agent log
  fetch('http://127.0.0.1:7864/ingest/9be3daa2-4225-4125-a8ee-f3740536c567',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'4e89a4'},body:JSON.stringify({sessionId:'4e89a4',runId:'pre-fix',hypothesisId,location,message,data,timestamp:Date.now()})}).catch(()=>{});
  // #endregion
}

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
  if (!pacer) {
    console.warn('[media-gateway] pacer ready no pacer', JSON.stringify({ call_id: id }));
    return;
  }
  pacer.ready = true;
  console.info('[media-gateway] pacer ready', JSON.stringify({ call_id: id, queue_len: pacer.queue.length }));
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
  emitDebugLog('H2', 'agent_playback_pacer.ts:enqueuePcm16Playback', 'pacer_enqueued_frames', {
    callId: id,
    pcm16Bytes: pcm16.length,
    framesAdded: frames.length,
    queueLen: pacer.queue.length,
    ready: pacer.ready,
  });

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
      if (active.queue.length % 10 === 1) {
        console.warn('[media-gateway] pacer blocked', JSON.stringify({ call_id: id, queue_len: active.queue.length, ready: active.ready }));
        emitDebugLog('H2', 'agent_playback_pacer.ts:tick', 'pacer_blocked_not_ready', {
          callId: id,
          queueLen: active.queue.length,
          ready: active.ready,
        });
      }
      return;
    }
    if (active.ws.readyState === active.ws.OPEN) {
      sendFrame(active.ws, frame);
    }
  }, tickMs);
}
