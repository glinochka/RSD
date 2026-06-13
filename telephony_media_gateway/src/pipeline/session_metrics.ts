export interface PipelineMetricsSnapshot {
  stt_partial_ms: number[];
  stt_final_ms: number[];
  vad_speech_ratio: number;
  vad_frames: number;
  vad_speech_frames: number;
}

export class SessionMetrics {
  private partialLatencies: number[] = [];
  private finalLatencies: number[] = [];
  private vadFrames = 0;
  private vadSpeechFrames = 0;

  recordPartial(latencyMs: number): void {
    this.partialLatencies.push(latencyMs);
  }

  recordFinal(latencyMs: number): void {
    this.finalLatencies.push(latencyMs);
  }

  recordVadFrame(isSpeech: boolean): void {
    this.vadFrames += 1;
    if (isSpeech) this.vadSpeechFrames += 1;
  }

  snapshot(): PipelineMetricsSnapshot {
    return {
      stt_partial_ms: [...this.partialLatencies],
      stt_final_ms: [...this.finalLatencies],
      vad_speech_ratio:
        this.vadFrames > 0 ? Math.round((this.vadSpeechFrames / this.vadFrames) * 1000) / 1000 : 0,
      vad_frames: this.vadFrames,
      vad_speech_frames: this.vadSpeechFrames,
    };
  }
}
