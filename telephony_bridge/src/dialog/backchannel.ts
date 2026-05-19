import { config } from '../config';
import type { BridgeAction } from '../providers/types';
import type { CallSession } from '../session/call_session';
import { voximplantTtsAdapter } from '../tts/adapter';

const ACK_PHRASES = ['Угу.', 'Понял.', 'Да-да.'];

export function maybeBackchannelAction(session: CallSession): BridgeAction | null {
  if (session.state !== 'LISTENING' || session.backchannelPlayed) {
    return null;
  }
  if (session.utteranceStartedAtMs === null) {
    return null;
  }
  const elapsed = Date.now() - session.utteranceStartedAtMs;
  if (elapsed < config.backchannelMinMs) {
    return null;
  }
  const voiceId = session.resolved?.voice_id ? String(session.resolved.voice_id) : undefined;
  const phrase = ACK_PHRASES[session.turnCount % ACK_PHRASES.length];
  session.backchannelPlayed = true;
  const action = voximplantTtsAdapter.playTtsAction(phrase, voiceId);
  action.interruptible = false;
  action.backchannel = true;
  return action;
}
