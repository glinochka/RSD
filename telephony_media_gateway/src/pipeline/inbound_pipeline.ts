import type { WebSocket } from 'ws';

import { ulawToPcm16 } from '../audio/ulaw';
import { config } from '../config';
import { createSttProvider } from '../stt/factory';
import type { StreamingSttSession } from '../stt/types';
import type { VadProcessor } from '../vad/types';
import { SessionMetrics } from './session_metrics';
import { BargeInDetector } from './barge_in_detector';
import { TurnTaking } from './turn_taking';

export interface InboundPipelineCallbacks {
  onPartial: (payload: { text: string; confidence?: number; stable?: boolean }) => void;
  onFinal: (payload: { text: string; confidence?: number }) => void;
  /** Fired when VAD sees speech during agent playback (stage 6). */
  onBargeIn?: (payload: { at_ms: number }) => void;
}

export class InboundPipeline {
  private readonly turnTaking: TurnTaking;
  private readonly metrics = new SessionMetrics();
  private stt: StreamingSttSession | null = null;
  private lastPartialText = '';
  private utteranceStartedAt = 0;
  private partialCount = 0;
  private readonly bargeIn: BargeInDetector | null;

  constructor(
    private readonly vad: VadProcessor,
    private readonly callbacks: InboundPipelineCallbacks,
    private readonly callId = '',
  ) {
    this.turnTaking = new TurnTaking(config.audioFrameMs, config.turnSilenceMs);
    this.bargeIn = callbacks.onBargeIn
      ? new BargeInDetector((payload) => callbacks.onBargeIn?.(payload))
      : null;
  }

  processUlawFrame(ulaw: Buffer): void {
    const pcm = ulawToPcm16(ulaw);
    const vadResult = this.vad.processFrame(pcm);
    this.metrics.recordVadFrame(vadResult.isSpeech);
    if (this.bargeIn && this.callId) {
      this.bargeIn.onVadFrame(this.callId, vadResult.isSpeech);
    }

    const turn = this.turnTaking.onVad(vadResult.isSpeech);
    if (turn === 'utterance_start') {
      this.startStt();
      this.utteranceStartedAt = Date.now();
      this.lastPartialText = '';
      this.partialCount = 0;
    }

    if (vadResult.isSpeech && this.stt) {
      const buf = Buffer.from(pcm.buffer, pcm.byteOffset, pcm.byteLength);
      this.stt.pushAudio(buf);
    }

    if (turn === 'utterance_end') {
      this.finishUtterance();
    }
  }

  private startStt(): void {
    this.closeStt();
    const provider = createSttProvider();
    const session = provider.startStream({
      sampleRate: this.vad.sampleRate,
      language: config.sttLanguage,
    });
    session.onPartial((p) => {
      this.lastPartialText = p.text;
      this.partialCount += 1;
      const latency = Date.now() - this.utteranceStartedAt;
      this.metrics.recordPartial(latency);
      this.callbacks.onPartial({
        text: p.text,
        confidence: p.confidence,
        stable: p.stable,
      });
    });
    session.onFinal((p) => {
      if (p.text.trim()) {
        this.lastPartialText = p.text;
      }
    });
    session.onError((err) => {
      console.warn('[media-gateway] STT stream error:', err.message);
    });
    this.stt = session;
  }

  private finishUtterance(): void {
    const finalLatency = Date.now() - this.utteranceStartedAt;
    this.metrics.recordFinal(finalLatency);
    const session = this.stt;
    this.stt = null;
    if (session) {
      session.onFinal((p) => {
        if (p.text.trim()) {
          this.lastPartialText = p.text;
        }
      });
      session.close();
    }
    const emit = () => {
      const text = this.lastPartialText.trim();
      this.turnTaking.reset();
      if (text) {
        this.callbacks.onFinal({ text, confidence: 0.9 });
        if (config.logLevel !== 'silent') {
          console.info(
            '[media-gateway] stt.final',
            JSON.stringify({
              text: text.slice(0, 120),
              stt_final_ms: finalLatency,
              partial_count: this.partialCount,
            }),
          );
        }
      }
      this.lastPartialText = '';
      this.partialCount = 0;
    };
    setTimeout(emit, config.sttFinalWaitMs);
  }

  close(): void {
    this.closeStt();
    this.bargeIn?.reset();
    this.vad.reset();
    this.turnTaking.reset();
    if (config.logLevel !== 'silent') {
      console.info('[media-gateway] pipeline metrics', JSON.stringify(this.metrics.snapshot()));
    }
  }

  getMetrics(): SessionMetrics {
    return this.metrics;
  }

  private closeStt(): void {
    if (this.stt) {
      try {
        this.stt.close();
      } catch {
        // ignore
      }
      this.stt = null;
    }
  }
}

export interface PipelineSessionRef {
  callId: string;
  connectionId: number;
  callerE164: string;
}

export function attachPipelineLogging(
  ws: WebSocket,
  sessionRef: PipelineSessionRef,
  getPipeline: () => InboundPipeline,
  onFinalToOrchestrator?: (payload: {
    text: string;
    confidence?: number;
    metrics?: { stt_final_ms: number; vad_speech_ratio: number };
  }) => void,
  onBargeIn?: (payload: { at_ms: number }) => void,
): InboundPipelineCallbacks {
  const callId = sessionRef.callId;
  return {
    onPartial(payload) {
      const snap = getPipeline().getMetrics().snapshot();
      const latency =
        snap.stt_partial_ms.length > 0 ? snap.stt_partial_ms[snap.stt_partial_ms.length - 1] : 0;
      if (config.logLevel !== 'silent') {
        const logEvery = config.sttPartialLogEvery;
        const n = snap.stt_partial_ms.length;
        if (n === 1 || n % logEvery === 0) {
          console.info(
            '[media-gateway] stt.partial',
            JSON.stringify({
              call_id: callId,
              text: payload.text.slice(0, 80),
              stt_partial_ms: latency,
            }),
          );
        }
      }
      if (ws.readyState === ws.OPEN) {
        ws.send(
          JSON.stringify({
            type: 'stt.partial',
            payload: { ...payload, call_id: callId },
          }),
        );
      }
    },
    onFinal(payload) {
      const snap = getPipeline().getMetrics().snapshot();
      const finalMs =
        snap.stt_final_ms.length > 0 ? snap.stt_final_ms[snap.stt_final_ms.length - 1] : 0;
      if (ws.readyState === ws.OPEN) {
        ws.send(
          JSON.stringify({
            type: 'stt.final',
            payload: {
              ...payload,
              call_id: callId,
              metrics: {
                stt_final_ms: finalMs,
                vad_speech_ratio: snap.vad_speech_ratio,
              },
            },
          }),
        );
      }
      onFinalToOrchestrator?.({
        ...payload,
        metrics: {
          stt_final_ms: finalMs,
          vad_speech_ratio: snap.vad_speech_ratio,
        },
      });
    },
    onBargeIn,
  };
}
