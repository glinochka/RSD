import type { WebSocket } from 'ws';

import { config } from '../config';
import {
  isPlaybackBlocked,
  isDownlinkReady,
  markAgentPlaybackEnd,
  markAgentPlaybackStart,
  markDownlinkReady,
} from './agent_playback_tracker';
import {
  clearPlaybackPacer,
  enqueuePcm16Playback,
  markPlaybackEnd,
  markPlaybackReady,
} from './agent_playback_pacer';
import { BINARY_FRAME_AUDIO_OUT } from '../protocol/events';
import {
  buildVoxMediaMessage,
  buildVoxStartMessage,
  buildVoxStopMessage,
} from '../ws/vox_media';
import { pcm16BufferToUlaw } from '../audio/ulaw';

function sendJson(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

function sendVoxDownlink(ws: WebSocket, message: string): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(message);
  }
}

function sendPcm16Frame(ws: WebSocket, frame: Buffer): void {
  if (!frame.length) return;
  // Last hop to Vox call stays in μ-law for reliable PSTN playout.
  const ulaw = pcm16BufferToUlaw(frame);
  if (!ulaw.length) return;
  sendVoxDownlink(ws, buildVoxMediaMessage(ulaw));
  if (config.loopbackTransport === 'binary' || config.loopbackTransport === 'both') {
    const binaryFrame = Buffer.allocUnsafe(1 + Math.floor(frame.length / 2));
    // binary loopback branch still expects μ-law payload for old tooling;
    // fill with silence-equivalent bytes to avoid bogus decoding.
    binaryFrame[0] = BINARY_FRAME_AUDIO_OUT;
    binaryFrame.fill(0xff, 1);
    ws.send(binaryFrame);
  }
}

function scheduleDownlinkReadyFallback(callId: string): void {
  setTimeout(() => {
    if (!isDownlinkReady(callId)) {
      markDownlinkReady(callId);
      markPlaybackReady(callId);
      if (config.logLevel !== 'silent') {
        console.warn(
          '[media-gateway] downlink.ready fallback',
          JSON.stringify({ call_id: callId, timeout_ms: config.downlinkReadyTimeoutMs }),
        );
      }
    }
  }, config.downlinkReadyTimeoutMs);
}

export function handleOrchestratorOutbound(
  ws: WebSocket,
  msg: { type?: string; call_id?: string; payload?: Record<string, unknown> },
): void {
  const type = String(msg.type || '').trim();
  const payload = msg.payload || {};
  const callId = String(msg.call_id || payload.call_id || '').trim();

  // After barge-in we intentionally drop only stale chunks/end of the interrupted turn.
  // The next agent.audio.start must pass through to reopen playback for a new reply.
  if (callId && type !== 'agent.audio.start' && isPlaybackBlocked(callId) && type.startsWith('agent.audio')) {
    return;
  }

  switch (type) {
    case 'agent.audio.start':
      if (callId) {
        clearPlaybackPacer(callId);
        markAgentPlaybackStart(callId);
      }
      // Keep explicit start/stop framing for Vox media WS parser.
      // (Barge-in filtering is handled upstream in Vox script side.)
      sendVoxDownlink(ws, buildVoxStartMessage());
      if (callId) {
        scheduleDownlinkReadyFallback(callId);
      }
      sendJson(ws, { type: 'agent.audio.start', payload: { ok: true, codec: payload.codec || 'pcmu' } });
      break;
    case 'agent.audio.chunk': {
      const b64 = String(payload.audio_pcm16_b64 || '').trim();
      if (b64 && callId) {
        enqueuePcm16Playback(ws, callId, Buffer.from(b64, 'base64'), sendPcm16Frame);
      }
      sendJson(ws, {
        type: 'agent.audio.chunk',
        payload: { ok: true, sequence: payload.sequence ?? 0 },
      });
      break;
    }
    case 'agent.audio.end':
      if (callId) {
        markAgentPlaybackEnd(callId);
        markPlaybackEnd(callId, () => {
          sendVoxDownlink(ws, buildVoxStopMessage());
          clearPlaybackPacer(callId);
        });
      }
      sendJson(ws, { type: 'agent.audio.end', payload: { ok: true, reason: payload.reason || 'complete' } });
      break;
    case 'agent.play_filler': {
      const b64 = String(payload.audio_pcm16_b64 || '').trim();
      if (b64 && callId) {
        sendVoxDownlink(ws, buildVoxStartMessage());
        scheduleDownlinkReadyFallback(callId);
        enqueuePcm16Playback(ws, callId, Buffer.from(b64, 'base64'), sendPcm16Frame);
        markPlaybackEnd(callId, () => {
          sendVoxDownlink(ws, buildVoxStopMessage());
          clearPlaybackPacer(callId);
        });
      }
      sendJson(ws, { type: 'agent.play_filler', payload: { ok: true, text: payload.text } });
      break;
    }
    case 'agent.turn_ready':
      sendJson(ws, { type: 'agent.turn_ready', payload });
      break;
    case 'call.transfer':
      sendJson(ws, { type: 'call.transfer', payload });
      break;
    default:
      break;
  }
}
