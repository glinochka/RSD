import crypto from 'crypto';
import { config } from './config';

function canonicalJson(data: Record<string, unknown>): string {
  return JSON.stringify(data, Object.keys(data).sort());
}

function internalHeaders(method: string, path: string, body: Record<string, unknown>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Internal-API-Key': config.backendInternalKey,
  };
  const timestamp = String(Math.floor(Date.now() / 1000));
  const bodyStr = canonicalJson(body);
  const payload = [method.toUpperCase(), path, timestamp, bodyStr].join('\n');
  const secret = config.signingSecret || config.backendInternalKey;
  const signature = crypto.createHmac('sha256', secret).update(payload, 'utf8').digest('hex');
  headers['X-Internal-Timestamp'] = timestamp;
  headers['X-Internal-Signature'] = signature;
  return headers;
}

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const url = `${config.backendUrl}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.backendRequestTimeoutMs);
  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: internalHeaders('POST', path, body),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Backend ${path} failed: ${response.status} ${text}`);
  }
  return (await response.json()) as T;
}

export async function fetchWebhookAuth(connectionId: number): Promise<{
  connection_id: number;
  webhook_secret: string;
  phone_number_e164: string;
  is_active: boolean;
}> {
  return postJson('/api/internal/telephony/webhook-auth', { connection_id: connectionId });
}

export async function telephonyResolve(params: {
  connection_id: number;
  caller_e164: string;
  call_id?: string;
}): Promise<Record<string, unknown>> {
  return postJson('/api/internal/telephony/resolve', params);
}

export async function telephonyCallEvent(params: Record<string, unknown>): Promise<{
  call_db_id: number;
  status: string;
  created: boolean;
}> {
  return postJson('/api/internal/telephony/call-event', params);
}

export async function telephonyPartial(params: {
  connection_id: number;
  call_db_id: number;
  caller_e164: string;
  transcript: string;
  is_final: boolean;
  confidence?: number;
  turn_index?: number;
}): Promise<{
  accepted: boolean;
  transcript: string;
  partial_count: number;
  is_final: boolean;
  suggest_backchannel?: boolean;
}> {
  return postJson('/api/internal/telephony/partial', params);
}

export async function telephonyTurn(params: {
  connection_id: number;
  call_db_id: number;
  caller_e164: string;
  user_transcript?: string;
  audio_base64?: string;
  recording_url?: string;
  turn_index?: number;
  streaming?: boolean;
  barged_in?: boolean;
  interrupted_agent_text?: string;
  dtmf_digit?: string;
}): Promise<{
  reply_text: string;
  reply_chunks?: string[];
  actions: Array<Record<string, unknown>>;
  stage: string;
  latency_ms?: number;
  play_filler?: boolean;
  partial_stt_count?: number;
  dialog_state?: string;
  use_ssml?: boolean;
}> {
  return postJson('/api/internal/telephony/turn', params);
}

export async function telephonyCancel(params: {
  connection_id: number;
  call_db_id: number;
}): Promise<{ cancelled: boolean }> {
  return postJson('/api/internal/telephony/cancel', params);
}
