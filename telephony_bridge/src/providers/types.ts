export type TelephonyWebhookEvent =
  | 'call.inbound'
  | 'call.answered'
  | 'call.hangup';

export type WebhookEnvelope = {
  schema_version: 1;
  event_id: string;
  event: TelephonyWebhookEvent;
  emitted_at: string;
  call_id: string;
  connection_id: number;
  payload: Record<string, unknown>;
};

export type BridgeAction =
  | { type: 'transfer'; e164: string }
  | { type: 'hangup'; reason?: string };

export interface TelephonyProvider {
  parseWebhookBody(body: unknown, pathConnectionId: number): WebhookEnvelope;
}
