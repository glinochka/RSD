import type { WebSocket } from 'ws';

import { config } from '../config';
import { attachPipelineLogging, InboundPipeline } from '../pipeline/inbound_pipeline';
import { isSttConfigured } from '../stt/factory';
import {
  BINARY_FRAME_AUDIO_IN,
  BINARY_FRAME_AUDIO_OUT,
  type ControlMessage,
  type SessionStartMessage,
  parseControlMessage,
  validateSessionStart,
} from '../protocol/events';
import { createVadProcessor } from '../vad/create';
import type { VadProcessor } from '../vad/types';
import { RtfTracker, expectedFrameBytes, shouldLogRtf } from './rtf_metrics';
import { emitBargeIn } from '../orch/barge_in_emit';
import { clearAgentPlayback } from '../orch/agent_playback_tracker';
import { publishOrchEvent } from '../orch/publisher';
import { clearPlaybackPacer } from '../orch/agent_playback_pacer';
import { registerReplySession, unregisterReplySession } from '../orch/reply_hub';
import { buildVoxMediaMessage, parseVoxMediaMessage } from './vox_media';

export interface MediaSession {
  callId: string;
  connectionId: number;
  callerE164: string;
  codec: 'pcmu' | 'pcma';
  startedAt: number;
  audioInFrames: number;
  audioOutFrames: number;
  rtf: RtfTracker;
  pipeline: InboundPipeline | null;
  vad: VadProcessor | null;
  useLoopback: boolean;
}

function sendJson(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

function sendError(ws: WebSocket, code: string, message: string): void {
  sendJson(ws, { type: 'error', payload: { code, message } });
}

function parseBinaryFrame(data: Buffer): { kind: number; payload: Buffer } | null {
  if (data.length < 2) return null;
  const kind = data[0];
  if (kind !== BINARY_FRAME_AUDIO_IN && kind !== BINARY_FRAME_AUDIO_OUT) {
    return null;
  }
  return { kind, payload: data.subarray(1) };
}

function buildBinaryOut(payload: Buffer): Buffer {
  const frame = Buffer.allocUnsafe(1 + payload.length);
  frame[0] = BINARY_FRAME_AUDIO_OUT;
  payload.copy(frame, 1);
  return frame;
}

function loopbackPayload(payload: Buffer): Buffer {
  if (config.loopbackMode === 'silence') {
    return Buffer.alloc(payload.length, 0xff);
  }
  return payload;
}

function emitLoopback(ws: WebSocket, session: MediaSession, payload: Buffer): void {
  const out = loopbackPayload(payload);
  if (out.length === 0) return;

  if (config.loopbackTransport === 'vox' || config.loopbackTransport === 'both') {
    ws.send(buildVoxMediaMessage(out));
  }
  if (config.loopbackTransport === 'binary' || config.loopbackTransport === 'both') {
    ws.send(buildBinaryOut(out));
  }
  session.audioOutFrames += 1;
}

function handleAudioIn(ws: WebSocket, session: MediaSession, payload: Buffer): void {
  session.audioInFrames += 1;
  const snap = session.rtf.recordFrame(payload.length);

  if (shouldLogRtf(session.audioInFrames)) {
    console.info(
      '[media-gateway] audio.in',
      JSON.stringify({
        call_id: session.callId,
        frames: snap.frames,
        bytes: payload.length,
        expected_frame_bytes: expectedFrameBytes(),
        rtf: snap.rtf,
        avg_rtf: session.rtf.averageRtf(),
      }),
    );
  }

  if (session.pipeline) {
    try {
      session.pipeline.processUlawFrame(payload);
    } catch (err) {
      console.warn(
        '[media-gateway] pipeline frame error',
        err instanceof Error ? err.message : err,
      );
    }
    return;
  }

  emitLoopback(ws, session, payload);
}

async function startPipelineSession(
  ws: WebSocket,
  base: Omit<MediaSession, 'pipeline' | 'vad' | 'useLoopback'>,
): Promise<MediaSession> {
  const vad = await createVadProcessor();
  let pipeline!: InboundPipeline;
  const sessionRef = {
    callId: base.callId,
    connectionId: base.connectionId,
    callerE164: base.callerE164,
  };
  pipeline = new InboundPipeline(
    vad,
    attachPipelineLogging(ws, sessionRef, () => pipeline, (payload) => {
      void publishOrchEvent({
        type: 'stt.final',
        call_id: base.callId,
        connection_id: base.connectionId,
        caller_e164: base.callerE164,
        payload,
      });
    }, (bargePayload) => {
      void emitBargeIn(ws, base, bargePayload);
    }),
    base.callId,
  );
  return {
    ...base,
    vad,
    pipeline,
    useLoopback: false,
  };
}

function pipelineActive(): boolean {
  if (!config.pipelineEnabled) return false;
  if (config.sttProvider === 'mock') return true;
  return isSttConfigured();
}

/**
 * Stage 2 loopback + Stage 3 VAD/STT/turn-taking on incoming μ-law.
 */
export function attachMediaSessionHandler(ws: WebSocket): void {
  let session: MediaSession | null = null;

  ws.on('message', (data, isBinary) => {
    if (isBinary) {
      if (!session) {
        sendError(ws, 'session_not_started', 'Send session.start before binary audio');
        return;
      }
      const buf = Buffer.isBuffer(data) ? data : Buffer.from(data as ArrayBuffer);
      const frame = parseBinaryFrame(buf);
      if (!frame || frame.kind !== BINARY_FRAME_AUDIO_IN) {
        sendError(ws, 'invalid_audio_frame', 'Expected audio.in binary frame');
        return;
      }
      handleAudioIn(ws, session, frame.payload);
      return;
    }

    const text = typeof data === 'string' ? data : data.toString('utf8');
    if (text.length > config.maxControlMessageBytes) {
      sendError(ws, 'message_too_large', 'Control message exceeds limit');
      return;
    }

    if (text === '{"type":"ping"}' || text === '{"type":"ping","payload":{}}') {
      sendJson(ws, { type: 'pong', payload: { ts: Date.now() } });
      return;
    }

    if (session) {
      const voxPayload = parseVoxMediaMessage(text);
      if (voxPayload === 'ignore') {
        return;
      }
      if (voxPayload && voxPayload.length > 0) {
        handleAudioIn(ws, session, voxPayload);
        return;
      }
    }

    const msg = parseControlMessage(text);
    if (!msg) {
      sendError(ws, 'invalid_control', 'Unknown or invalid control message');
      return;
    }

    void handleControl(ws, msg, () => session, (s) => {
      session = s;
    });
  });

  ws.on('close', () => {
    if (session) {
      session.pipeline?.close();
      void publishOrchEvent({
        type: 'session.end',
        call_id: session.callId,
        connection_id: session.connectionId,
        caller_e164: session.callerE164,
        payload: { reason: 'ws_close' },
      });
      unregisterReplySession(session.callId);
      clearPlaybackPacer(session.callId);
      clearAgentPlayback(session.callId);
      if (config.logLevel !== 'silent') {
        console.info(
          '[media-gateway] session closed',
          JSON.stringify({
            call_id: session.callId,
            audio_in_frames: session.audioInFrames,
            audio_out_frames: session.audioOutFrames,
            avg_rtf: session.rtf.averageRtf(),
            duration_ms: Date.now() - session.startedAt,
            pipeline: Boolean(session.pipeline),
            metrics: session.pipeline?.getMetrics().snapshot(),
          }),
        );
      }
    }
    session = null;
  });
}

async function handleControl(
  ws: WebSocket,
  msg: ControlMessage,
  getSession: () => MediaSession | null,
  setSession: (s: MediaSession | null) => void,
): Promise<void> {
  switch (msg.type) {
    case 'session.start': {
      if (getSession()) {
        sendError(ws, 'session_already_started', 'Close connection before a new session.start');
        return;
      }
      const err = validateSessionStart(msg as SessionStartMessage);
      if (err) {
        sendError(ws, 'invalid_session_start', err);
        return;
      }
      const p = (msg as SessionStartMessage).payload;
      const base = {
        callId: p.call_id.trim(),
        connectionId: p.connection_id,
        callerE164: p.caller_e164.trim(),
        codec: p.codec,
        startedAt: Date.now(),
        audioInFrames: 0,
        audioOutFrames: 0,
        rtf: new RtfTracker(),
      };

      let next: MediaSession;
      if (pipelineActive()) {
        try {
          next = await startPipelineSession(ws, base);
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          sendError(ws, 'pipeline_init_failed', message);
          return;
        }
      } else {
        next = {
          ...base,
          pipeline: null,
          vad: null,
          useLoopback: true,
        };
        if (config.logLevel !== 'silent') {
          console.warn(
            '[media-gateway] pipeline disabled or STT not configured — loopback mode',
          );
        }
      }

      setSession(next);
      registerReplySession(next.callId, ws);
      void publishOrchEvent({
        type: 'session.start',
        call_id: next.callId,
        connection_id: next.connectionId,
        caller_e164: next.callerE164,
        payload: { codec: next.codec },
      });
      sendJson(ws, {
        type: 'session.start',
        payload: {
          ok: true,
          call_id: next.callId,
          protocol_version: p.protocol_version || '1',
          audio_frame_ms: config.audioFrameMs,
          loopback_transport: next.useLoopback ? config.loopbackTransport : null,
          pipeline: Boolean(next.pipeline),
          stt_provider: next.pipeline ? config.sttProvider : null,
          turn_silence_ms: config.turnSilenceMs,
        },
      });
      if (config.logLevel !== 'silent') {
        console.info(
          '[media-gateway] session.start',
          JSON.stringify({
            call_id: next.callId,
            connection_id: next.connectionId,
            codec: next.codec,
            pipeline: Boolean(next.pipeline),
            stt_provider: config.sttProvider,
          }),
        );
      }
      break;
    }
    case 'session.end': {
      const s = getSession();
      if (!s) {
        sendError(ws, 'session_not_started', 'No active session');
        return;
      }
      s.pipeline?.close();
      sendJson(ws, { type: 'session.end', payload: { ok: true, call_id: s.callId } });
      setSession(null);
      ws.close(1000, 'session.end');
      break;
    }
    case 'dtmf': {
      const s = getSession();
      const digit =
        msg.type === 'dtmf' && 'payload' in msg && msg.payload && 'digit' in msg.payload
          ? String((msg.payload as { digit?: string }).digit || '')
          : '';
      if (config.logLevel !== 'silent') {
        console.info('[media-gateway] dtmf', JSON.stringify({ call_id: s?.callId, digit }));
      }
      if (s && digit) {
        void publishOrchEvent({
          type: 'dtmf',
          call_id: s.callId,
          connection_id: s.connectionId,
          caller_e164: s.callerE164,
          payload: { digit },
        });
      }
      sendJson(ws, { type: 'dtmf', payload: { ok: true, digit } });
      break;
    }
    case 'agent.audio.start':
    case 'agent.audio.chunk':
    case 'agent.audio.end':
    case 'agent.play_filler':
    case 'agent.turn_ready':
      sendError(ws, 'invalid_direction', `${msg.type} is emitted by orchestrator, not accepted from client`);
      break;
    case 'barge_in':
      sendError(
        ws,
        'invalid_direction',
        'barge_in is emitted by gateway on subscriber speech during agent.audio.*',
      );
      break;
    case 'stt.partial':
    case 'stt.final':
      sendError(ws, 'invalid_direction', `${msg.type} is emitted by gateway, not accepted from client`);
      break;
    default:
      sendError(ws, 'unsupported', `Unsupported control type: ${(msg as ControlMessage).type}`);
  }
}
