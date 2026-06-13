import { config } from '../config';
import { DeepgramStreamingStt } from './deepgram_stream';
import { MockStreamingStt } from './mock_stream';
import type { StreamingSttProvider } from './types';
import { YandexStreamingStt } from './yandex_stream';

export function createSttProvider(): StreamingSttProvider {
  const provider = config.sttProvider;
  switch (provider) {
    case 'yandex':
      return new YandexStreamingStt();
    case 'deepgram':
      return new DeepgramStreamingStt();
    case 'mock':
      return new MockStreamingStt();
    default:
      throw new Error(`Unknown STT_PROVIDER: ${provider}`);
  }
}

export function isSttConfigured(): boolean {
  if (config.sttProvider === 'mock') return true;
  if (config.sttProvider === 'yandex') return Boolean(config.yandexSpeechkitApiKey);
  if (config.sttProvider === 'deepgram') return Boolean(config.deepgramApiKey);
  return false;
}
