import { telephonyPartial } from '../backend_client';
import type { BridgeAction } from '../providers/types';
import type { WebhookEnvelope } from '../providers/types';
import type { CallSession } from '../session/call_session';
import { isBackendUnavailableError } from '../resilience';
import { handleBargeInDuringSpeech } from './barge_in';
import { maybeBackchannelAction } from './backchannel';

export async function handlePartialTranscript(
  session: CallSession,
  envelope: WebhookEnvelope,
  callerE164: string,
): Promise<BridgeAction[]> {
  if (!session.callDbId) {
    return [];
  }

  const transcript = String(
    envelope.payload.transcript || envelope.payload.user_transcript || '',
  ).trim();
  if (!transcript) {
    return [];
  }

  if (session.state === 'SPEAKING') {
    return handleBargeInDuringSpeech(session, transcript);
  }

  const isFinal = Boolean(envelope.payload.is_final);
  if (session.utteranceStartedAtMs === null) {
    session.utteranceStartedAtMs = Date.now();
    session.backchannelPlayed = false;
  }
  session.partialTranscript = transcript;
  const confRaw = envelope.payload.confidence;
  if (confRaw !== undefined && confRaw !== null && confRaw !== '') {
    const conf = Number(confRaw);
    if (Number.isFinite(conf)) {
      session.partialConfidence = conf;
    }
  }

  const actions: BridgeAction[] = [];
  try {
    const partial = await telephonyPartial({
      connection_id: session.connectionId,
      call_db_id: session.callDbId,
      caller_e164: callerE164,
      transcript,
      is_final: isFinal,
      confidence: session.partialConfidence ?? undefined,
      turn_index: session.turnCount,
    });
    if (partial.suggest_backchannel) {
      const ack = maybeBackchannelAction(session);
      if (ack) {
        actions.push(ack);
      }
    }
  } catch (err) {
    if (!isBackendUnavailableError(err)) {
      throw err;
    }
  }
  return actions;
}
