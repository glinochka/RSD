import fs from 'fs';

import * as ort from 'onnxruntime-node';

import type { VadFrameResult, VadProcessor } from './types';

const SAMPLE_RATE = 8000;
const WINDOW_SAMPLES = 256;

/**
 * Silero VAD (ONNX). Model: https://github.com/snakers4/silero-vad
 */
export class SileroVad implements VadProcessor {
  readonly sampleRate = SAMPLE_RATE;
  readonly frameSamples = WINDOW_SAMPLES;

  private session: ort.InferenceSession | null = null;
  private h: ort.Tensor | null = null;
  private c: ort.Tensor | null = null;
  private pending = new Int16Array(0);
  private lastProbability = 0;

  constructor(
    private readonly modelPath: string,
    private readonly speechThreshold: number,
  ) {}

  static async create(modelPath: string, speechThreshold: number): Promise<SileroVad> {
    const vad = new SileroVad(modelPath, speechThreshold);
    await vad.init();
    return vad;
  }

  private async init(): Promise<void> {
    if (!fs.existsSync(this.modelPath)) {
      throw new Error(`Silero VAD model not found: ${this.modelPath}`);
    }
    this.session = await ort.InferenceSession.create(this.modelPath, {
      executionProviders: ['cpu'],
    });
    this.resetStates();
  }

  private resetStates(): void {
    this.h = new ort.Tensor('float32', new Float32Array(2 * 1 * 64).fill(0), [2, 1, 64]);
    this.c = new ort.Tensor('float32', new Float32Array(2 * 1 * 64).fill(0), [2, 1, 64]);
  }

  processFrame(pcm: Int16Array): VadFrameResult {
    if (!this.session || !this.h || !this.c) {
      return { isSpeech: false, probability: 0 };
    }

    const merged = new Int16Array(this.pending.length + pcm.length);
    merged.set(this.pending, 0);
    merged.set(pcm, this.pending.length);
    this.pending = merged;

    while (this.pending.length >= WINDOW_SAMPLES) {
      const chunk = this.pending.subarray(0, WINDOW_SAMPLES);
      this.pending = this.pending.subarray(WINDOW_SAMPLES);
      const floats = new Float32Array(WINDOW_SAMPLES);
      for (let i = 0; i < WINDOW_SAMPLES; i += 1) {
        floats[i] = chunk[i]! / 32768;
      }
      const input = new ort.Tensor('float32', floats, [1, WINDOW_SAMPLES]);
      const sr = new ort.Tensor('int64', BigInt64Array.from([BigInt(SAMPLE_RATE)]), []);
      const feeds: Record<string, ort.Tensor> = {
        input,
        sr,
        h: this.h,
        c: this.c,
      };
      const out = this.session.runSync(feeds);
      const probTensor = (out.output ?? out.prob ?? Object.values(out)[0]) as ort.Tensor;
      const prob = Number(probTensor.data[0]);
      const nextH = (out.hn ?? out.h ?? out._hn) as ort.Tensor | undefined;
      const nextC = (out.cn ?? out.c ?? out._cn) as ort.Tensor | undefined;
      if (nextH) this.h = nextH;
      if (nextC) this.c = nextC;
      this.lastProbability = prob;
    }

    return {
      isSpeech: this.lastProbability >= this.speechThreshold,
      probability: this.lastProbability,
    };
  }

  reset(): void {
    this.pending = new Int16Array(0);
    this.lastProbability = 0;
    this.resetStates();
  }
}

export async function tryCreateSileroVad(
  modelPath: string,
  speechThreshold: number,
): Promise<SileroVad | null> {
  try {
    return await SileroVad.create(modelPath, speechThreshold);
  } catch (err) {
    console.warn(
      '[media-gateway] Silero VAD unavailable, using energy VAD:',
      err instanceof Error ? err.message : err,
    );
    return null;
  }
}
