import fs from 'fs';

import * as ort from 'onnxruntime-node';

import type { VadFrameResult, VadProcessor } from './types';

const SAMPLE_RATE = 8000;
const WINDOW_SAMPLES = 256;
/** Silero ONNX context length @ 8 kHz (see silero-vad OnnxWrapper). */
const CONTEXT_SAMPLES = 32;
const STATE_DIM = 128;

/**
 * Silero VAD (ONNX). Model: https://github.com/snakers4/silero-vad
 */
export class SileroVad implements VadProcessor {
  readonly sampleRate = SAMPLE_RATE;
  readonly frameSamples = WINDOW_SAMPLES;

  private session: ort.InferenceSession | null = null;
  private state: ort.Tensor | null = null;
  private context = new Float32Array(CONTEXT_SAMPLES);
  private pending = new Int16Array(0);
  private lastProbability = 0;
  /** Serialize async ONNX runs (onnxruntime-node ≥1.20 has no runSync). */
  private inferChain: Promise<void> = Promise.resolve();

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
    this.state = new ort.Tensor(
      'float32',
      new Float32Array(2 * 1 * STATE_DIM).fill(0),
      [2, 1, STATE_DIM],
    );
    this.context = new Float32Array(CONTEXT_SAMPLES);
  }

  processFrame(pcm: Int16Array): VadFrameResult {
    if (!this.session || !this.state) {
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
      this.scheduleInfer(floats);
    }

    return {
      isSpeech: this.lastProbability >= this.speechThreshold,
      probability: this.lastProbability,
    };
  }

  private scheduleInfer(floats: Float32Array): void {
    this.inferChain = this.inferChain
      .then(() => this.inferWindow(floats))
      .catch((err) => {
        console.warn(
          '[media-gateway] Silero infer failed:',
          err instanceof Error ? err.message : err,
        );
      });
  }

  private async inferWindow(floats: Float32Array): Promise<void> {
    if (!this.session || !this.state) return;

    const inputLen = CONTEXT_SAMPLES + WINDOW_SAMPLES;
    const inputData = new Float32Array(inputLen);
    inputData.set(this.context, 0);
    inputData.set(floats, CONTEXT_SAMPLES);

    const input = new ort.Tensor('float32', inputData, [1, inputLen]);
    const sr = new ort.Tensor('int64', BigInt64Array.from([BigInt(SAMPLE_RATE)]), []);
    const feeds: Record<string, ort.Tensor> = {
      input,
      state: this.state,
      sr,
    };

    const out =
      typeof this.session.runSync === 'function'
        ? this.session.runSync(feeds)
        : await this.session.run(feeds);

    const probTensor = (out.output ?? out.prob ?? Object.values(out)[0]) as ort.Tensor;
    const prob = Number(probTensor.data[0]);
    const nextState = (out.stateN ?? out.state_out) as ort.Tensor | undefined;
    if (nextState) {
      this.state = nextState;
    }
    this.context = inputData.subarray(inputLen - CONTEXT_SAMPLES);
    this.lastProbability = prob;
  }

  reset(): void {
    this.pending = new Int16Array(0);
    this.lastProbability = 0;
    this.inferChain = Promise.resolve();
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
