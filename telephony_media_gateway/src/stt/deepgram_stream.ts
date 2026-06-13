import WebSocket from 'ws';

import { config } from '../config';
import type { StreamingSttProvider, StreamingSttSession, SttPartial } from './types';

export class DeepgramStreamingStt implements StreamingSttProvider {
  readonly name = 'deepgram';

  startStream(opts: { sampleRate: number; language: string }): StreamingSttSession {
    const apiKey = config.deepgramApiKey;
    if (!apiKey) {
      throw new Error('DEEPGRAM_API_KEY is required for STT_PROVIDER=deepgram');
    }

    const lang = opts.language.startsWith('ru') ? 'ru' : opts.language;
    const params = new URLSearchParams({
      encoding: 'linear16',
      sample_rate: String(opts.sampleRate),
      channels: '1',
      language: lang,
      interim_results: 'true',
      punctuate: 'true',
      endpointing: 'false',
    });

    const ws = new WebSocket(`wss://api.deepgram.com/v1/listen?${params.toString()}`, {
      headers: { Authorization: `Token ${apiKey}` },
    });

    let partialCb: ((p: SttPartial) => void) | null = null;
    let finalCb: ((p: SttPartial) => void) | null = null;
    let errorCb: ((err: Error) => void) | null = null;
    let closed = false;

    ws.on('message', (raw) => {
      try {
        const msg = JSON.parse(String(raw)) as {
          type?: string;
          channel?: { alternatives?: Array<{ transcript?: string; confidence?: number }> };
          is_final?: boolean;
        };
        const alt = msg.channel?.alternatives?.[0];
        const text = (alt?.transcript || '').trim();
        if (!text) return;
        const payload: SttPartial = {
          text,
          confidence: alt?.confidence,
          stable: Boolean(msg.is_final),
        };
        if (msg.is_final) {
          finalCb?.(payload);
        } else {
          partialCb?.(payload);
        }
      } catch {
        // ignore malformed
      }
    });

    ws.on('error', (err) => {
      errorCb?.(err instanceof Error ? err : new Error(String(err)));
    });

    return {
      pushAudio(pcm16: Buffer) {
        if (closed || ws.readyState !== WebSocket.OPEN) return;
        ws.send(pcm16);
      },
      close() {
        if (closed) return;
        closed = true;
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'CloseStream' }));
          ws.close();
        }
      },
      onPartial(cb) {
        partialCb = cb;
      },
      onFinal(cb) {
        finalCb = cb;
      },
      onError(cb) {
        errorCb = cb;
      },
    };
  }
}
