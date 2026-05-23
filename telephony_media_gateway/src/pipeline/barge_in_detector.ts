/**
 * Detect subscriber speech during agent playback → barge_in (stage 6).
 */
import { config } from '../config';
import {
  agentPlaybackStartedAt,
  isAgentPlaybackActive,
  markBargeInFired,
} from '../orch/agent_playback_tracker';

export type BargeInHandler = (payload: { at_ms: number }) => void;

export class BargeInDetector {
  private speechFrames = 0;
  private fired = false;

  constructor(private readonly onBargeIn: BargeInHandler) {}

  onVadFrame(callId: string, isSpeech: boolean): void {
    if (!config.bargeInEnabled || this.fired) return;
    if (!isAgentPlaybackActive(callId)) {
      this.speechFrames = 0;
      return;
    }
    if (!isSpeech) {
      this.speechFrames = 0;
      return;
    }
    this.speechFrames += 1;
    if (this.speechFrames < config.bargeInSpeechFrames) {
      return;
    }
    if (!markBargeInFired(callId)) {
      return;
    }
    this.fired = true;
    const started = agentPlaybackStartedAt(callId);
    const atMs = started > 0 ? Math.max(0, Date.now() - started) : 0;
    this.onBargeIn({ at_ms: atMs });
  }

  reset(): void {
    this.speechFrames = 0;
    this.fired = false;
  }
}
