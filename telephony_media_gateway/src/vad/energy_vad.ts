import type { VadFrameResult, VadProcessor } from './types';

/**
 * Lightweight energy-based VAD (fallback when Silero ONNX model is unavailable).
 */
export class EnergyVad implements VadProcessor {
  readonly sampleRate = 8000;
  readonly frameSamples: number;

  constructor(
    frameMs: number,
    private readonly threshold: number,
  ) {
    this.frameSamples = Math.max(80, Math.floor((this.sampleRate * frameMs) / 1000));
  }

  processFrame(pcm: Int16Array): VadFrameResult {
    if (pcm.length === 0) {
      return { isSpeech: false, probability: 0 };
    }
    let sum = 0;
    for (let i = 0; i < pcm.length; i += 1) {
      const s = pcm[i]! / 32768;
      sum += s * s;
    }
    const rms = Math.sqrt(sum / pcm.length);
    const probability = Math.min(1, rms / this.threshold);
    return { isSpeech: probability >= 0.5, probability };
  }

  reset(): void {
    // stateless
  }
}
