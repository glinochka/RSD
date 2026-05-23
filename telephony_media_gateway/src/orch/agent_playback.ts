import type { WebSocket } from 'ws';

import { config } from '../config';
import {
  isPlaybackBlocked,
  markAgentPlaybackEnd,
  markAgentPlaybackStart,
} from './agent_playback_tracker';
import { buildVoxMediaMessage } from '../ws/vox_media';

function sendJson(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

function sendUlawPayload(ws: WebSocket, ulaw: Buffer): void {
  if (!ulaw.length) return;
  if (config.loopbackTransport === 'vox' || config.loopbackTransport === 'both') {
    ws.send(buildVoxMediaMessage(ulaw));
  }
  if (config.loopbackTransport === 'binary' || config.loopbackTransport === 'both') {
    const frame = Buffer.allocUnsafe(1 + ulaw.length);
    frame[0] = 0x02;
    ulaw.copy(frame, 1);
    ws.send(frame);
  }
}

export function handleOrchestratorOutbound(
  ws: WebSocket,
  msg: { type?: string; call_id?: string; payload?: Record<string, unknown> },
): void {
  const type = String(msg.type || '').trim();
  const payload = msg.payload || {};
  const callId = String(msg.call_id || payload.call_id || '').trim();

  if (callId && isPlaybackBlocked(callId) && type.startsWith('agent.audio')) {
    return;
  }

  switch (type) {
    case 'agent.audio.start':
      if (callId) markAgentPlaybackStart(callId);
      sendJson(ws, { type: 'agent.audio.start', payload: { ok: true, codec: payload.codec || 'pcmu' } });
      break;
    case 'agent.audio.chunk': {
      const b64 = String(payload.audio_b64 || '').trim();
      if (b64) {
        sendUlawPayload(ws, Buffer.from(b64, 'base64'));
      }
      sendJson(ws, {
        type: 'agent.audio.chunk',
        payload: { ok: true, sequence: payload.sequence ?? 0 },
      });
      break;
    }
    case 'agent.audio.end':
      if (callId) markAgentPlaybackEnd(callId);
      sendJson(ws, { type: 'agent.audio.end', payload: { ok: true, reason: payload.reason || 'complete' } });
      break;
    case 'agent.play_filler': {
      const b64 = String(payload.audio_b64 || '').trim();
      if (b64) {
        sendUlawPayload(ws, Buffer.from(b64, 'base64'));
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
