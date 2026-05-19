import { telephonyTurn } from '../backend_client';
import { config } from '../config';
import type { BridgeAction } from '../providers/types';
import type { WebhookEnvelope } from '../providers/types';
import type { CallSession } from '../session/call_session';
import {
  callDurationExceededActions,
  maxTurnsExceededActions,
  mergeTurnResponseActions,
} from './actions';
import { isBackendUnavailableError, backendUnavailableActions } from '../resilience';

export async function handleUserRecordingTurn(
  session: CallSession,
  envelope: WebhookEnvelope,
  callerE164: string,
): Promise<BridgeAction[]> {
  if (!session.callDbId) {
    return [];
  }

  if (session.isCallExpired(config.maxCallMinutes)) {
    return callDurationExceededActions(session);
  }

  if (session.isMaxTurns(config.maxTurns)) {
    return maxTurnsExceededActions(session);
  }

  const leg = String(envelope.payload.leg || 'user_turn').trim();
  if (leg !== 'user_turn') {
    return [];
  }

  try {
    session.transition('PROCESSING');
  } catch {
    // ignore invalid transition
  }

  const userTranscript = String(
    envelope.payload.user_transcript ||
      envelope.payload.transcript ||
      session.partialTranscript ||
      '',
  ).trim();
  const audioBase64 = envelope.payload.audio_base64
    ? String(envelope.payload.audio_base64)
    : undefined;
  const recordingUrl = envelope.payload.recording_url
    ? String(envelope.payload.recording_url)
    : undefined;

  let turn: {
    reply_text: string;
    actions: Array<Record<string, unknown>>;
    stage: string;
    latency_ms?: number;
  };

  const bargedIn = session.bargedInPending;
  const interrupted = session.interruptedAgentText || undefined;
  session.bargedInPending = false;
  session.interruptedAgentText = '';
  session.utteranceStartedAtMs = null;
  session.backchannelPlayed = false;

  session.activeTurnAbort = new AbortController();
  try {
    turn = await telephonyTurn({
      connection_id: session.connectionId,
      call_db_id: session.callDbId,
      caller_e164: callerE164,
      user_transcript: userTranscript || undefined,
      audio_base64: audioBase64,
      recording_url: recordingUrl,
      turn_index: session.turnCount,
      streaming: config.streamingEnabled,
      barged_in: bargedIn,
      interrupted_agent_text: interrupted,
    });
  } catch (err) {
    if (isBackendUnavailableError(err)) {
      return backendUnavailableActions();
    }
    throw err;
  } finally {
    session.activeTurnAbort = null;
  }

  if (turn.stage !== 'stt_empty') {
    session.incrementTurn();
    session.partialTranscript = '';
    session.partialConfidence = null;
  }

  try {
    session.transition('SPEAKING');
  } catch {
    // ignore
  }

  const actions = mergeTurnResponseActions(session, turn);

  if (turn.stage === 'stt_empty') {
    session.sttEmptyCount += 1;
    try {
      session.transition('LISTENING');
    } catch {
      // ignore
    }
    return actions;
  }
  session.sttEmptyCount = 0;

  const terminal = actions.some((action) => action.type === 'transfer' || action.type === 'hangup');
  if (!terminal) {
    try {
      session.transition('LISTENING');
    } catch {
      // ignore
    }
  }

  return actions;
}
