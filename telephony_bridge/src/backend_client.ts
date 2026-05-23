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

export async function telephonyResolveInbound(params: {
  connection_id: number;
  called_e164?: string;
  sip_from?: string;
  sip_to?: string;
}): Promise<{ connection_id: number; routed_by: 'did' | 'sip' | 'webhook' }> {
  return postJson('/api/internal/telephony/resolve-inbound', params);
}

export async function telephonyResolve(params: {
  connection_id: number;
  caller_e164: string;
  called_e164?: string;
  call_id?: string;
  routed_agent_id?: number;
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

export async function telephonyCancel(params: {
  connection_id: number;
  call_db_id: number;
}): Promise<{ cancelled: boolean }> {
  return postJson('/api/internal/telephony/cancel', params);
}
