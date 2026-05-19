export type TelephonyWebhookEvent =
  | 'call.inbound'
  | 'call.answered'
  | 'call.recording_ready'
  | 'call.partial_transcript'
  | 'call.hangup'
  | 'dtmf';

export interface WebhookEnvelope {
  schema_version: number;
  event_id: string;
  event: TelephonyWebhookEvent;
  emitted_at: string;
  call_id: string;
  connection_id: number;
  payload: Record<string, unknown>;
}

export interface BridgeAction {
  type: string;
  [key: string]: unknown;
}

export interface WebhookHandlerResult {
  ok: boolean;
  actions: BridgeAction[];
}

export interface TelephonyProvider {
  parseWebhookBody(body: unknown, pathConnectionId: number): WebhookEnvelope;
  /** CPaaS plays synthesized speech (MVP: Voximplant TTS in VoxEngine). */
  playAudio?(text: string, voiceId?: string): BridgeAction;
  transfer?(e164: string): BridgeAction;
  startMediaStream?(): BridgeAction;
}
