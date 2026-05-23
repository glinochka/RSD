import { config } from '../config';
import { EnergyVad } from './energy_vad';
import { tryCreateSileroVad } from './silero_vad';
import type { VadProcessor } from './types';

export async function createVadProcessor(): Promise<VadProcessor> {
  const silero = await tryCreateSileroVad(config.vadModelPath, config.vadSpeechThreshold);
  if (silero) {
    console.info('[media-gateway] VAD: Silero ONNX', config.vadModelPath);
    return silero;
  }
  console.info('[media-gateway] VAD: energy fallback');
  return new EnergyVad(config.audioFrameMs, config.vadEnergyThreshold);
}
