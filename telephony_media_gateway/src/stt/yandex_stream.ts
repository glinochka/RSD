import path from 'path';

import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';

import { config } from '../config';
import type { StreamingSttProvider, StreamingSttSession, SttPartial } from './types';

const YANDEX_STT_HOST = 'stt.api.cloud.yandex.net:443';
const PROTO_PATH = path.join(__dirname, '../../proto/yandex_stt_v3_minimal.proto');

type GrpcStreamingRequest = {
  session_options?: {
    recognition_model?: {
      model?: string;
      audio_format?: { raw_audio?: { audio_encoding?: number; sample_rate_hertz?: number; audio_channel_count?: number } };
      language_restriction?: { restriction_type?: number; language_code?: string[] };
      audio_processing_type?: number;
    };
  };
  chunk?: { data?: Buffer };
};

type GrpcStreamingResponse = {
  partial?: { alternatives?: Array<{ text?: string; confidence?: number }> };
  final?: { alternatives?: Array<{ text?: string; confidence?: number }> };
};

let cachedPackage: grpc.GrpcObject | null = null;

function loadPackage(): grpc.GrpcObject {
  if (cachedPackage) return cachedPackage;
  const def = protoLoader.loadSync(PROTO_PATH, {
    keepCase: false,
    longs: String,
    enums: Number,
    defaults: true,
    oneofs: true,
  });
  cachedPackage = grpc.loadPackageDefinition(def) as grpc.GrpcObject;
  return cachedPackage;
}

function buildMetadata(): grpc.Metadata {
  const meta = new grpc.Metadata();
  const key = config.yandexSpeechkitApiKey;
  if (!key) {
    throw new Error('YANDEX_SPEECHKIT_API_KEY is required for STT_PROVIDER=yandex');
  }
  meta.add('authorization', `Api-Key ${key}`);
  const folder = config.yandexSpeechkitFolderId;
  if (folder) {
    meta.add('x-folder-id', folder);
  }
  return meta;
}

function altText(update?: { alternatives?: Array<{ text?: string; confidence?: number }> }): SttPartial | null {
  const alt = update?.alternatives?.[0];
  const text = (alt?.text || '').trim();
  if (!text) return null;
  return { text, confidence: alt?.confidence, stable: true };
}

export class YandexStreamingStt implements StreamingSttProvider {
  readonly name = 'yandex';

  startStream(opts: { sampleRate: number; language: string }): StreamingSttSession {
    const pkg = loadPackage() as unknown as {
      speechkit: { stt: { v3: { Recognizer: new (...args: unknown[]) => grpc.Client } } };
    };
    const Recognizer = pkg.speechkit.stt.v3.Recognizer;
    const client = new Recognizer(YANDEX_STT_HOST, grpc.credentials.createSsl()) as grpc.Client & {
      RecognizeStreaming: (
        metadata: grpc.Metadata,
      ) => grpc.ClientDuplexStream<GrpcStreamingRequest, GrpcStreamingResponse>;
    };
    const call = client.RecognizeStreaming(buildMetadata()) as grpc.ClientDuplexStream<
      GrpcStreamingRequest,
      GrpcStreamingResponse
    >;

    let partialCb: ((p: SttPartial) => void) | null = null;
    let finalCb: ((p: SttPartial) => void) | null = null;
    let errorCb: ((err: Error) => void) | null = null;
    let sessionReady = false;
    let closed = false;

    const lang = opts.language || config.sttLanguage;

    call.write({
      session_options: {
        recognition_model: {
          model: 'general',
          audio_format: {
            raw_audio: {
              audio_encoding: 1,
              sample_rate_hertz: opts.sampleRate,
              audio_channel_count: 1,
            },
          },
          language_restriction: {
            restriction_type: 1,
            language_code: [lang],
          },
          audio_processing_type: 1,
        },
      },
    });
    sessionReady = true;

    call.on('data', (resp: GrpcStreamingResponse) => {
      const partial = altText(resp.partial);
      if (partial) {
        partial.stable = false;
        partialCb?.(partial);
        return;
      }
      const fin = altText(resp.final);
      if (fin) {
        finalCb?.(fin);
      }
    });

    call.on('error', (err: Error) => {
      errorCb?.(err);
    });

    return {
      pushAudio(pcm16: Buffer) {
        if (closed || !sessionReady) return;
        call.write({ chunk: { data: pcm16 } });
      },
      close() {
        if (closed) return;
        closed = true;
        call.end();
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
