export const MSG_BACKEND_UNAVAILABLE =
  'Сервис временно недоступен. Сейчас соединю с оператором.';

export const MSG_CPAAS_TIMEOUT = 'Извините, соединение прервано. До свидания.';

import type { BridgeAction } from './providers/types';

export function backendUnavailableActions(): BridgeAction[] {
  return [
    { type: 'play_tts', text: MSG_BACKEND_UNAVAILABLE },
    { type: 'transfer', e164: 'operator' },
  ];
}

export function cpaasTimeoutActions(): BridgeAction[] {
  return [
    { type: 'play_tts', text: MSG_CPAAS_TIMEOUT },
    { type: 'hangup', reason: 'timeout' },
  ];
}

export function isBackendUnavailableError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return (
    msg.includes('failed') ||
    msg.includes('econnrefused') ||
    msg.includes('fetch failed') ||
    msg.includes('network') ||
    msg.includes('502') ||
    msg.includes('503') ||
    msg.includes('504')
  );
}
