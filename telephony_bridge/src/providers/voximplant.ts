import type { TelephonyProvider, TelephonyWebhookEvent, WebhookEnvelope } from './types';

const EVENTS = new Set<TelephonyWebhookEvent>(['call.inbound', 'call.answered', 'call.hangup']);

function asObject(body: unknown): Record<string, unknown> {
  if (body && typeof body === 'object' && !Array.isArray(body)) {
    return body as Record<string, unknown>;
  }
  throw new Error('Invalid JSON body');
}

export const voximplantProvider: TelephonyProvider = {
  parseWebhookBody(body: unknown, pathConnectionId: number): WebhookEnvelope {
    const data = asObject(body);
    const schemaVersion = Number(data.schema_version ?? 0);
    if (schemaVersion !== 1 && schemaVersion !== 2) {
      throw new Error('Unsupported schema_version');
    }
    const event = String(data.event || '').trim() as TelephonyWebhookEvent;
    if (!EVENTS.has(event)) {
      throw new Error(`Unknown event: ${event}`);
    }
    const connectionId = Number(data.connection_id);
    if (!Number.isFinite(connectionId) || connectionId !== pathConnectionId) {
      throw new Error('connection_id mismatch');
    }
    const callId = String(data.call_id || '').trim();
    if (!callId) {
      throw new Error('call_id is required');
    }
    const eventId = String(data.event_id || '').trim();
    if (!eventId) {
      throw new Error('event_id is required');
    }
    return {
      schema_version: 1,
      event_id: eventId,
      event,
      emitted_at: String(data.emitted_at || new Date().toISOString()),
      call_id: callId,
      connection_id: connectionId,
      payload: asObject(data.payload ?? {}),
    };
  },
};
