/**
 * Detect subscriber speech during agent playback → barge_in (stage 6).
 */
import { config } from '../config';
import {
  agentPlaybackStartedAt,
  isAgentPlaybackActive,
  lastDtmfAt,
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
    const now = Date.now();
    const started = agentPlaybackStartedAt(callId);
    if (started > 0) {
      const sinceStart = now - started;
      if (sinceStart < config.bargeInPlaybackGraceMs) {
        this.speechFrames = 0;
        if (config.logLevel !== 'silent') {
          console.info(
            '[media-gateway] barge_in suppressed',
            JSON.stringify({
              call_id: callId,
              reason: 'playback_grace',
              since_start_ms: sinceStart,
              grace_ms: config.bargeInPlaybackGraceMs,
            }),
          );
        }
        return;
      }
    }
    const dtmfAt = lastDtmfAt(callId);
    if (dtmfAt > 0) {
      const sinceDtmf = now - dtmfAt;
      if (sinceDtmf < config.bargeInDtmfSuppressMs) {
        this.speechFrames = 0;
        if (config.logLevel !== 'silent') {
          console.info(
            '[media-gateway] barge_in suppressed',
            JSON.stringify({
              call_id: callId,
              reason: 'dtmf_suppress',
              since_dtmf_ms: sinceDtmf,
              suppress_ms: config.bargeInDtmfSuppressMs,
            }),
          );
        }
        return;
      }
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
    const atMs = started > 0 ? Math.max(0, Date.now() - started) : 0;
    this.onBargeIn({ at_ms: atMs });
  }

  reset(): void {
    this.speechFrames = 0;
    this.fired = false;
  }
}
