import { config } from '../config';
import { EnergyVad } from './energy_vad';
import { tryCreateSileroVad } from './silero_vad';
import type { VadProcessor } from './types';

class HybridVad implements VadProcessor {
  readonly sampleRate: number;
  readonly frameSamples: number;

  constructor(
    private readonly primary: VadProcessor,
    private readonly energy: EnergyVad,
  ) {
    this.sampleRate = primary.sampleRate;
    this.frameSamples = primary.frameSamples;
  }

  processFrame(pcm: Int16Array) {
    const silero = this.primary.processFrame(pcm);
    const energy = this.energy.processFrame(pcm);
    // Keep Silero as primary signal, but recover short/quiet utterances
    // when model confidence is too low on telephony line.
    const energyAssist = energy.probability >= 0.55;
    const isSpeech = silero.isSpeech || energyAssist;
    return {
      isSpeech,
      probability: Math.max(silero.probability, energy.probability),
    };
  }

  reset(): void {
    this.primary.reset();
    this.energy.reset();
  }
}

export async function createVadProcessor(): Promise<VadProcessor> {
  const energy = new EnergyVad(config.audioFrameMs, config.vadEnergyThreshold);
  const silero = await tryCreateSileroVad(config.vadModelPath, config.vadSpeechThreshold);
  if (silero) {
    console.info('[media-gateway] VAD: Silero ONNX + energy assist', config.vadModelPath);
    return new HybridVad(silero, energy);
  }
  console.info('[media-gateway] VAD: energy fallback');
  return energy;
}
