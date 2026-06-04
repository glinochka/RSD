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

const debugFrameLogByCall = new Map<string, number>();

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

function sendJson(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

function sendVoxDownlink(ws: WebSocket, message: string): void {
  if (ws.readyState === ws.OPEN) {
    console.info('[media-gateway] vox send', JSON.stringify({ msg: message.slice(0, 100) }));
    emitDebugLog('H4', 'agent_playback.ts:sendVoxDownlink', 'sending_vox_message', {
      readyState: ws.readyState,
      preview: message.slice(0, 80),
      messageLength: message.length,
    });
    ws.send(message);
  } else {
    console.warn('[media-gateway] vox send skipped', JSON.stringify({ readyState: ws.readyState }));
    emitDebugLog('H4', 'agent_playback.ts:sendVoxDownlink', 'vox_send_skipped_socket_not_open', {
      readyState: ws.readyState,
      messageLength: message.length,
    });
  }
}

function sendPcm16Frame(ws: WebSocket, frame: Buffer): void {
  if (!frame.length) return;
  // Last hop to Vox call stays in μ-law for reliable PSTN playout.
  const ulaw = pcm16BufferToUlaw(frame);
  if (!ulaw.length) return;
  let absSumLe = 0;
  let absSumBe = 0;
  const sampleCount = Math.floor(frame.length / 2);
  for (let i = 0; i + 1 < frame.length; i += 2) {
    absSumLe += Math.abs(frame.readInt16LE(i));
    absSumBe += Math.abs(frame.readInt16BE(i));
  }
  const meanAbsLe = sampleCount > 0 ? Math.round(absSumLe / sampleCount) : 0;
  const meanAbsBe = sampleCount > 0 ? Math.round(absSumBe / sampleCount) : 0;
  emitDebugLog('H3', 'agent_playback.ts:sendPcm16Frame', 'pcm16_to_ulaw_converted', {
    pcm16Bytes: frame.length,
    ulawBytes: ulaw.length,
    meanAbsLe,
    meanAbsBe,
    firstUlawByte: ulaw[0] ?? null,
  });
  const callIdForLog = String((ws as unknown as { __callId?: string }).__callId || '');
  const prevLogged = debugFrameLogByCall.get(callIdForLog) || 0;
  if (config.logLevel !== 'silent' && prevLogged < 5) {
    debugFrameLogByCall.set(callIdForLog, prevLogged + 1);
    console.info(
      '[media-gateway] debug pcm16 stats',
      JSON.stringify({
        hypothesis: 'H3',
        call_id: callIdForLog || null,
        frame_index: prevLogged,
        pcm16_bytes: frame.length,
        ulaw_bytes: ulaw.length,
        mean_abs_le: meanAbsLe,
        mean_abs_be: meanAbsBe,
      }),
    );
  }
  console.info('[media-gateway] vox frame', JSON.stringify({ len: ulaw.length }));
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
  if (callId) {
    (ws as unknown as { __callId?: string }).__callId = callId;
  }

  // After barge-in we intentionally drop only stale chunks/end of the interrupted turn.
  // The next agent.audio.start must pass through to reopen playback for a new reply.
  if (callId && type !== 'agent.audio.start' && isPlaybackBlocked(callId) && type.startsWith('agent.audio')) {
    return;
  }

  switch (type) {
    case 'agent.audio.start':
      emitDebugLog('H2', 'agent_playback.ts:handleOrchestratorOutbound:start', 'agent_audio_start_received', {
        callId,
        codec: payload.codec || 'pcmu',
      });
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
      const payloadKeys = Object.keys(payload);
      if (config.logLevel !== 'silent' && (payload.sequence ?? 0) < 3) {
        console.info(
          '[media-gateway] debug orch chunk payload',
          JSON.stringify({
            hypothesis: 'H1',
            call_id: callId,
            sequence: payload.sequence ?? 0,
            payload_keys: payloadKeys,
            b64_len: b64.length,
          }),
        );
      }
      emitDebugLog('H1', 'agent_playback.ts:handleOrchestratorOutbound:chunk', 'agent_audio_chunk_received', {
        callId,
        hasB64: Boolean(b64),
        b64Length: b64.length,
        sequence: payload.sequence ?? 0,
      });
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
