import { telephonyCancel } from '../backend_client';
import { config } from '../config';
import type { BridgeAction } from '../providers/types';
import type { CallSession } from '../session/call_session';

export function stopTtsAction(): BridgeAction {
  return { type: 'stop_tts' };
}

export function abortActiveTurn(session: CallSession): void {
  if (session.activeTurnAbort) {
    session.activeTurnAbort.abort();
    session.activeTurnAbort = null;
  }
}

export async function handleBargeInDuringSpeech(
  session: CallSession,
  transcript: string,
): Promise<BridgeAction[]> {
  if (!config.bargeInEnabled || session.state !== 'SPEAKING') {
    return [];
  }
  const text = transcript.trim();
  if (text.length < 2) {
    return [];
  }

  abortActiveTurn(session);
  session.bargedInPending = true;
  session.partialTranscript = text;

  if (session.callDbId) {
    try {
      await telephonyCancel({
        connection_id: session.connectionId,
        call_db_id: session.callDbId,
      });
    } catch {
      // Best-effort cancel; bridge still stops TTS locally.
    }
  }

  try {
    session.transition('LISTENING');
  } catch {
    // ignore
  }

  return [stopTtsAction()];
}
