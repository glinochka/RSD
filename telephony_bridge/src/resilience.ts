export const MSG_BACKEND_UNAVAILABLE =
  'Сервис временно недоступен. Сейчас соединю с оператором.';

export const MSG_CPAAS_TIMEOUT = 'Извините, соединение прервано. До свидания.';

/** Control-only bridge: VoxEngine reads these fields (not legacy `actions`). */
export type ControlDegradedHints = {
  degraded: true;
  transfer_e164: string;
};

export function backendUnavailableControlHints(
  operatorE164 = 'operator',
): ControlDegradedHints {
  return {
    degraded: true,
    transfer_e164: operatorE164.trim() || 'operator',
  };
}

export function isBackendUnavailableError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  // Auth/config errors (401/403) are not transient — do not enter degraded transfer.
  if (msg.includes(' 401 ') || msg.includes(' 403 ') || msg.includes('invalid internal')) {
    return false;
  }
  return (
    msg.includes('econnrefused') ||
    msg.includes('fetch failed') ||
    msg.includes('network') ||
    msg.includes('aborted') ||
    msg.includes(' 500 ') ||
    msg.includes(' 502 ') ||
    msg.includes(' 503 ') ||
    msg.includes(' 504 ')
  );
}
