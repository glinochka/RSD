import { RECORDING_DISCLAIMER_RU, shouldPlayRecordingDisclaimer } from '../compliance';
import { config, recordSilenceSecFromConfig } from '../config';
import type { BridgeAction } from '../providers/types';
import type { CallSession } from '../session/call_session';
import { config } from '../config';
import { voximplantTtsAdapter } from '../tts/adapter';

export function buildRecordAction(): BridgeAction {
  return {
    type: 'record',
    max_sec: config.recordMaxSec,
    silence_sec: recordSilenceSecFromConfig(),
    endpointing: true,
  };
}

export function buildAnsweredActions(session: CallSession): BridgeAction[] {
  const actions: BridgeAction[] = [];
  const resolved = session.resolved || {};
  const voiceId = resolved.voice_id ? String(resolved.voice_id) : undefined;

  if (
    !session.disclaimerPlayed &&
    shouldPlayRecordingDisclaimer({
      recordCalls: Boolean(resolved.record_calls),
      disclaimerPlayed: Boolean(resolved.disclaimer_played),
    })
  ) {
    actions.push(voximplantTtsAdapter.playTtsAction(RECORDING_DISCLAIMER_RU, voiceId));
    session.disclaimerPlayed = true;
  }

  const welcome = String(resolved.welcome_message || '').trim();
  if (welcome) {
    actions.push(voximplantTtsAdapter.playTtsAction(welcome, voiceId));
  }

  return actions;
}

export function buildListenAfterGreetingActions(session: CallSession): BridgeAction[] {
  return [...buildAnsweredActions(session), buildRecordAction()];
}

export function resolveTransferE164(session: CallSession, raw: unknown): string {
  const value = String(raw || '').trim();
  if (!value || value === 'operator') {
    return String(session.resolved?.operator_transfer_e164 || 'operator').trim() || 'operator';
  }
  return value;
}

function ttsAction(text: string, voiceId?: string, useSsml?: boolean): BridgeAction {
  const action = voximplantTtsAdapter.playTtsAction(text, voiceId);
  if (useSsml ?? config.ssmlEnabled) {
    action.ssml = true;
  }
  return action;
}

export function mergeTurnResponseActions(
  session: CallSession,
  turn: {
    reply_text?: string;
    reply_chunks?: string[];
    actions?: Array<Record<string, unknown>>;
    play_filler?: boolean;
    use_ssml?: boolean;
  },
): BridgeAction[] {
  const voiceId = session.resolved?.voice_id ? String(session.resolved.voice_id) : undefined;
  const useSsml = Boolean(turn.use_ssml ?? config.ssmlEnabled);
  const actions: BridgeAction[] = [];
  const spokenParts: string[] = [];

  for (const item of turn.actions || []) {
    const type = String(item.type || '').trim();
    if (type === 'play_filler') {
      const text = String(item.text || 'Секунду, смотрю в расписании…').trim();
      actions.push(ttsAction(text, voiceId, useSsml));
      spokenParts.push(text);
    }
    if (type === 'enable_dtmf') {
      actions.push({
        type: 'enable_dtmf',
        digits: String(item.digits || '120'),
      });
    }
  }

  if (turn.play_filler && !actions.some((a) => a.type === 'play_tts')) {
    const filler = 'Секунду, смотрю в расписании…';
    actions.push(ttsAction(filler, voiceId, useSsml));
    spokenParts.push(filler);
  }

  const chunks = (turn.reply_chunks || [])
    .map((c) => String(c || '').trim())
    .filter(Boolean);
  if (chunks.length > 0) {
    for (const chunk of chunks) {
      actions.push(ttsAction(chunk, voiceId, useSsml));
      spokenParts.push(chunk);
    }
  } else {
    const reply = String(turn.reply_text || '').trim();
    if (reply) {
      actions.push(ttsAction(reply, voiceId, useSsml));
      spokenParts.push(reply);
    }
  }
  if (spokenParts.length > 0) {
    session.interruptedAgentText = spokenParts.join(' ').slice(0, 500);
    session.speakingStartedAtMs = Date.now();
  }

  for (const item of turn.actions || []) {
    const type = String(item.type || '').trim();
    if (type === 'play_filler') {
      continue;
    }
    if (type === 'transfer') {
      actions.push({ type: 'transfer', e164: resolveTransferE164(session, item.e164) });
    } else if (type === 'hangup') {
      actions.push({ type: 'hangup', reason: String(item.reason || 'agent') });
    } else if (type === 'play_url' && item.url) {
      actions.push({ type: 'play_url', url: String(item.url) });
    } else if (type === 'play_tts' && item.text) {
      actions.push(ttsAction(String(item.text), voiceId, useSsml));
    }
  }

  const terminal = actions.some((action) => action.type === 'transfer' || action.type === 'hangup');
  if (!terminal) {
    actions.push(buildRecordAction());
  }
  return actions;
}

export function maxTurnsExceededActions(session: CallSession): BridgeAction[] {
  const voiceId = session.resolved?.voice_id ? String(session.resolved.voice_id) : undefined;
  return [
    voximplantTtsAdapter.playTtsAction(
      'Мы обсудили основные вопросы. Спасибо за звонок. До свидания!',
      voiceId,
    ),
    { type: 'hangup', reason: 'max_turns' },
  ];
}

export function callDurationExceededActions(session: CallSession): BridgeAction[] {
  const voiceId = session.resolved?.voice_id ? String(session.resolved.voice_id) : undefined;
  return [
    voximplantTtsAdapter.playTtsAction('Время разговора истекло. До свидания!', voiceId),
    { type: 'hangup', reason: 'max_call_duration' },
  ];
}

export function transferOperatorAction(session: CallSession): BridgeAction {
  return { type: 'transfer', e164: resolveTransferE164(session, 'operator') };
}
