export interface VadFrameResult {
  isSpeech: boolean;
  probability: number;
}

export interface VadProcessor {
  readonly sampleRate: number;
  readonly frameSamples: number;
  /** Feed one PCM16 frame; returns speech probability for this step. */
  processFrame(pcm: Int16Array): VadFrameResult;
  reset(): void;
}
