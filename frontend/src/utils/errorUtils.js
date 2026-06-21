/**
 * Error handling utilities aligned with FastAPI exception responses.
 * FastAPI returns { detail: string | Array<{ loc, msg, type, ... }> }.
 */

/**
 * Normalize FastAPI response body detail to a single user-facing string.
 * - detail as string → return as-is
 * - detail as array (e.g. Pydantic validation) → first item's msg or loc, or join
 * @param {string|Array<{ msg?: string, loc?: string[] }>} detail - response.data.detail
 * @returns {string}
 */
export function normalizeDetail(detail) {
  if (detail == null) return '';
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail) || detail.length === 0) return '';
  const first = detail[0];
  if (first?.msg) return first.msg;
  if (first?.loc && Array.isArray(first.loc)) {
    const locStr = first.loc.join('. ');
    return first.msg ? `${locStr}: ${first.msg}` : locStr;
  }
  return JSON.stringify(detail);
}

/**
 * Get user-friendly message from an API error response (status + data).
 * Prefers backend detail (normalized), then falls back to status-based defaults.
 * @param {number} status - HTTP status
 * @param {object} data - response.data (may have detail, message)
 * @param {Record<number, string>} fallbacks - optional map status → message
 * @returns {string}
 */
export function getApiErrorMessage(status, data, fallbacks = {}) {
  const rawDetail = data?.detail ?? data?.message;
  if (rawDetail != null) {
    const normalized = typeof rawDetail === 'string' ? rawDetail : normalizeDetail(rawDetail);
    if (normalized) return normalized;
  }
  return fallbacks[status] ?? '';
}

export function isWhatsappUserbotAuthSessionExpiredMessage(message) {
  const lower = String(message || '').trim().toLowerCase();
  return lower.includes('истекла') || lower.includes('не найдена') || lower.includes('expired');
}

export default { normalizeDetail, getApiErrorMessage, isWhatsappUserbotAuthSessionExpiredMessage };
