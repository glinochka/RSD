import type { BridgeAction } from '../providers/types';
import type { CallSession } from '../session/call_session';
import { telephonyTurn } from '../backend_client';
import { config } from '../config';
import { mergeTurnResponseActions, transferOperatorAction } from './actions';
import { isBackendUnavailableError, backendUnavailableActions } from '../resilience';

export async function handleDtmfDigit(
  session: CallSession,
  digit: string,
  callerE164: string,
): Promise<BridgeAction[]> {
  const d = String(digit || '').trim();
  if (!session.callDbId) {
    return [];
  }

  if (d === '2' || d === '0') {
    return [transferOperatorAction(session)];
  }

  if (d !== '1') {
    return [];
  }

  try {
    const turn = await telephonyTurn({
      connection_id: session.connectionId,
      call_db_id: session.callDbId,
      caller_e164: callerE164,
      dtmf_digit: '1',
      turn_index: session.turnCount,
      streaming: config.streamingEnabled,
    });
    session.incrementTurn();
    return mergeTurnResponseActions(session, turn);
  } catch (err) {
    if (isBackendUnavailableError(err)) {
      return backendUnavailableActions();
    }
    throw err;
  }
}
