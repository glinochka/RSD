import { telephonyCallEvent, telephonyResolve, telephonyResolveInbound } from './backend_client';
import {
  backendUnavailableControlHints,
  isBackendUnavailableError,
} from './resilience';
import type { CallSession } from './session/call_session';
import type { WebhookEnvelope } from './providers/types';

const SIGNAL_EVENTS = new Set(['call.inbound', 'call.answered', 'call.hangup']);

export function isSignalEvent(event: string): boolean {
  return SIGNAL_EVENTS.has(event);
}

export type ControlWebhookResult = {
  callEvent: { call_db_id: number; status: string; created: boolean } | null;
  actions: Array<Record<string, unknown>>;
  hangupStatus?: string;
  degraded?: boolean;
  transfer_e164?: string;
};

export async function handleSignalWebhook(params: {
  envelope: WebhookEnvelope;
  session: CallSession;
  callerE164: string;
  connectionId: number;
  onInbound?: () => void;
  onHangup?: (status: string) => void;
}): Promise<ControlWebhookResult> {
  const { envelope, session, callerE164 } = params;
  let connectionId = params.connectionId;
  const calledE164 = String(
    envelope.payload.called_e164 || envelope.payload.called_number || '',
  ).trim();
  const sipFrom = String(envelope.payload.sip_from || envelope.payload.sipFrom || '').trim();
  const sipTo = String(envelope.payload.sip_to || envelope.payload.sipTo || '').trim();
  const actions: Array<Record<string, unknown>> = [];

  let hangupStatus: string | undefined;
  if (envelope.event === 'call.hangup') {
    const reason = String(envelope.payload.reason || 'completed').toLowerCase();
    if (reason === 'transferred') {
      hangupStatus = 'transferred';
    } else if (reason === 'failed' || reason === 'timeout' || reason === 'no_answer') {
      hangupStatus = 'failed';
    } else {
      hangupStatus = 'completed';
    }
    params.onHangup?.(hangupStatus);
  }

  const statusMap: Record<string, string | undefined> = {
    'call.inbound': 'ringing',
    'call.answered': 'active',
    'call.hangup': hangupStatus,
  };

  let callEvent: { call_db_id: number; status: string; created: boolean } | null = null;
  if (envelope.event === 'call.inbound') {
    params.onInbound?.();
  }

  if (envelope.event === 'call.inbound' || envelope.event === 'call.answered') {
    try {
      const inbound = await telephonyResolveInbound({
        connection_id: connectionId,
        called_e164: calledE164 || undefined,
        sip_from: sipFrom || undefined,
        sip_to: sipTo || undefined,
      });
      connectionId = inbound.connection_id;
    } catch (err) {
      console.error('resolve-inbound failed', err instanceof Error ? err.message : err);
      if (isBackendUnavailableError(err) && envelope.event === 'call.inbound') {
        const hints = backendUnavailableControlHints();
        return { callEvent: null, actions, ...hints };
      }
    }
  }

  try {
    callEvent = await telephonyCallEvent({
      connection_id: connectionId,
      external_call_id: envelope.call_id,
      caller_e164: callerE164,
      called_e164: calledE164 || undefined,
      event: envelope.event,
      status: statusMap[envelope.event],
      duration_sec:
        envelope.payload.duration_sec !== undefined
          ? Number(envelope.payload.duration_sec)
          : undefined,
      metadata: {
        event_id: envelope.event_id,
        emitted_at: envelope.emitted_at,
        bridge_state: session.state,
        control_only: true,
        called_e164: calledE164 || undefined,
        sip_from: sipFrom || undefined,
        sip_to: sipTo || undefined,
      },
    });
    session.callDbId = callEvent.call_db_id;
  } catch (err) {
    console.error('call-event failed', err instanceof Error ? err.message : err);
    if (isBackendUnavailableError(err) && envelope.event === 'call.inbound') {
      const hints = backendUnavailableControlHints(
        session.resolved?.operator_transfer_e164,
      );
      return { callEvent: null, actions, ...hints };
    }
    throw err;
  }

  if (envelope.event === 'call.inbound' || envelope.event === 'call.answered') {
    try {
      const resolved = await telephonyResolve({
        connection_id: connectionId,
        caller_e164: callerE164,
        called_e164: calledE164 || undefined,
        call_id: envelope.call_id,
      });
      session.resolved = {
        welcome_message: resolved.welcome_message as string | null | undefined,
        voice_id: resolved.voice_id as string | undefined,
        record_calls: Boolean(resolved.record_calls),
        disclaimer_played: Boolean(resolved.disclaimer_played),
        operator_transfer_e164: resolved.operator_transfer_e164 as string | undefined,
      };
    } catch (err) {
      console.error('resolve failed', err instanceof Error ? err.message : err);
      if (isBackendUnavailableError(err)) {
        const hints = backendUnavailableControlHints(
          session.resolved?.operator_transfer_e164,
        );
        return { callEvent, actions, ...hints, hangupStatus };
      }
    }
  }

  if (envelope.event === 'call.answered') {
    session.markAnswered();
  }

  return { callEvent, actions, hangupStatus };
}
