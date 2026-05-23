/**
 * Media session protocol v1 — control JSON + binary audio frames.
 * Canonical spec: docs/telephony/SESSION_PROTOCOL.md
 */

export const PROTOCOL_VERSION = '1';

/** JSON control messages (WebSocket text frames). */
export type ControlEventType =
  | 'session.start'
  | 'session.end'
  | 'stt.partial'
  | 'stt.final'
  | 'agent.audio.start'
  | 'agent.audio.chunk'
  | 'agent.audio.end'
  | 'barge_in'
  | 'dtmf'
  | 'error'
  | 'ping'
  | 'pong';

export interface SessionStartPayload {
  call_id: string;
  connection_id: number;
  caller_e164: string;
  codec: 'pcmu' | 'pcma';
  called_number?: string;
  protocol_version?: string;
}

export interface SessionStartMessage {
  type: 'session.start';
  payload: SessionStartPayload;
}

export interface SessionEndMessage {
  type: 'session.end';
  payload?: { reason?: string };
}

export interface SttPartialMessage {
  type: 'stt.partial';
  payload: { text: string; confidence?: number; stable?: boolean };
}

export interface SttFinalMessage {
  type: 'stt.final';
  payload: { text: string; confidence?: number };
}

export interface AgentAudioStartMessage {
  type: 'agent.audio.start';
  payload?: { codec?: 'pcmu' | 'pcma' };
}

export interface AgentAudioChunkMessage {
  type: 'agent.audio.chunk';
  payload?: { sequence?: number };
}

export interface AgentAudioEndMessage {
  type: 'agent.audio.end';
  payload?: { reason?: string };
}

export interface BargeInMessage {
  type: 'barge_in';
  payload?: { at_ms?: number };
}

export interface DtmfMessage {
  type: 'dtmf';
  payload: { digit: string };
}

export interface ErrorMessage {
  type: 'error';
  payload: { code: string; message: string };
}

export type ControlMessage =
  | SessionStartMessage
  | SessionEndMessage
  | SttPartialMessage
  | SttFinalMessage
  | AgentAudioStartMessage
  | AgentAudioChunkMessage
  | AgentAudioEndMessage
  | BargeInMessage
  | DtmfMessage
  | ErrorMessage;

/**
 * Binary WebSocket frames (opcode binary).
 * First byte = frame kind; remainder = payload.
 * See SESSION_PROTOCOL.md § Binary frames.
 */
export const BINARY_FRAME_AUDIO_IN = 0x01;
export const BINARY_FRAME_AUDIO_OUT = 0x02;

export function isControlEventType(value: string): value is ControlEventType {
  return [
    'session.start',
    'session.end',
    'stt.partial',
    'stt.final',
    'agent.audio.start',
    'agent.audio.chunk',
    'agent.audio.end',
    'barge_in',
    'dtmf',
    'error',
    'ping',
    'pong',
  ].includes(value);
}

export function parseControlMessage(raw: string): ControlMessage | null {
  try {
    const data = JSON.parse(raw) as { type?: string };
    const type = String(data.type || '').trim();
    if (!isControlEventType(type) || type === 'ping' || type === 'pong') {
      return null;
    }
    return data as ControlMessage;
  } catch {
    return null;
  }
}

export function validateSessionStart(msg: SessionStartMessage): string | null {
  const p = msg.payload;
  if (!p?.call_id?.trim()) return 'call_id required';
  if (!Number.isFinite(p.connection_id) || p.connection_id <= 0) {
    return 'connection_id must be positive integer';
  }
  if (!p.caller_e164?.trim()) return 'caller_e164 required';
  if (p.codec !== 'pcmu' && p.codec !== 'pcma') return 'codec must be pcmu or pcma';
  return null;
}
