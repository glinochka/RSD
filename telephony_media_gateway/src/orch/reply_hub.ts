import type { WebSocket } from 'ws';
import Redis from 'ioredis';

import { config } from '../config';
import { handleOrchestratorOutbound } from './agent_playback';

let subscriber: Redis | null = null;
const sessions = new Map<string, WebSocket>();

function sendJson(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

export function registerReplySession(callId: string, ws: WebSocket): void {
  sessions.set(callId, ws);
  console.info('[media-gateway] reply session registered', JSON.stringify({ call_id: callId, total_sessions: sessions.size }));
}

export function unregisterReplySession(callId: string): void {
  const deleted = sessions.delete(callId);
  console.info('[media-gateway] reply session unregistered', JSON.stringify({ call_id: callId, deleted, remaining_sessions: sessions.size }));
}

export async function startReplySubscriber(): Promise<void> {
  if (!config.orchEventsEnabled || !config.redisUrl) {
    console.warn('[media-gateway] orch reply subscriber disabled (no REDIS_URL)');
    return;
  }
  subscriber = new Redis(config.redisUrl, { maxRetriesPerRequest: 2, lazyConnect: true });
  await subscriber.connect();
  await subscriber.subscribe(config.orchRepliesChannel);
  subscriber.on('message', (_channel, raw) => {
    try {
      const msg = JSON.parse(raw) as { call_id?: string; type?: string; payload?: Record<string, unknown> };
      const callId = String(msg.call_id || '').trim();
      const eventType = String(msg.type || 'agent.turn_ready').trim();
      console.info('[media-gateway] orch reply received', JSON.stringify({ type: eventType, call_id: callId, has_session: sessions.has(callId), active_sessions: sessions.size }));
      if (!callId) {
        console.warn('[media-gateway] orch reply missing call_id');
        return;
      }
      const ws = sessions.get(callId);
      if (!ws) {
        console.warn('[media-gateway] orch reply session not found', JSON.stringify({ call_id: callId, type: eventType, registered_calls: Array.from(sessions.keys()) }));
        return;
      }
      handleOrchestratorOutbound(ws, {
        type: eventType,
        call_id: callId,
        payload: (msg.payload as Record<string, unknown>) || {},
      });
    } catch (err) {
      console.warn('[media-gateway] orch reply parse error', err instanceof Error ? err.message : err);
    }
  });
  console.info('[media-gateway] subscribed to orchestrator replies');
}
