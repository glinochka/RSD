import type { BridgeAction } from '../providers/types';

/** MVP TTS via CPaaS (Voximplant). Other providers can be added behind this interface. */
export interface TtsAdapter {
  playTtsAction(text: string, voiceId?: string): BridgeAction;
}

export const voximplantTtsAdapter: TtsAdapter = {
  playTtsAction(text: string, voiceId?: string): BridgeAction {
    const action: BridgeAction = { type: 'play_tts', text: text.trim() };
    if (voiceId) {
      action.voice_id = voiceId;
    }
    return action;
  },
};
