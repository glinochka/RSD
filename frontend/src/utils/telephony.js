/** Telephony UI helpers */

export const TELEPHONY_PROVIDER = 'telephony_voximplant';

export function maskE164(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (digits.length < 8) return '***';
  return `+${digits.slice(0, 4)}***${digits.slice(-4)}`;
}

export function findTelephonyChannel(channels) {
  const list = Array.isArray(channels) ? channels : [];
  return list.find((c) => c?.provider === TELEPHONY_PROVIDER) || null;
}

export function telephonyStatusLabel(status) {
  const map = {
    ringing: 'Звонит',
    active: 'В разговоре',
    completed: 'Завершён',
    failed: 'Ошибка',
    transferred: 'Переведён',
  };
  return map[status] || status || '—';
}

export async function copyTextToClipboard(text) {
  const value = String(text || '').trim();
  if (!value) return false;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return true;
  }
  return false;
}
