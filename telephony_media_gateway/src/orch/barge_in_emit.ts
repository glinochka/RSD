import type { WebSocket } from 'ws';

import { config } from '../config';
import { publishOrchEvent } from './publisher';

export async function emitBargeIn(
  ws: WebSocket,
  session: { callId: string; connectionId: number; callerE164: string },
  payload: { at_ms: number },
): Promise<void> {
  const inner = { at_ms: payload.at_ms };
  void publishOrchEvent({
    type: 'barge_in',
    call_id: session.callId,
    connection_id: session.connectionId,
    caller_e164: session.callerE164,
    payload: inner,
  });
  if (ws.readyState === ws.OPEN) {
    ws.send(
      JSON.stringify({
        type: 'barge_in',
        payload: { ...inner, clear_playback: true },
      }),
    );
  }
  if (config.logLevel !== 'silent') {
    console.info(
      '[media-gateway] barge_in',
      JSON.stringify({ call_id: session.callId, at_ms: payload.at_ms }),
    );
  }
}
