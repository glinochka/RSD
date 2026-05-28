/**
 * Capture ?ref= from URL and persist for registration attribution.
 */

import { getStorageItem, removeStorageItem, setStorageItem } from './storage';

export const REFERRAL_STORAGE_KEY = 'referral_code';
const REFERRAL_TTL_MS = 30 * 24 * 60 * 60 * 1000;

export function normalizeReferralCode(value) {
  if (!value || typeof value !== 'string') return null;
  const cleaned = value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
  return cleaned || null;
}

export function captureReferralFromSearch(search) {
  const params = new URLSearchParams(search || '');
  const ref = normalizeReferralCode(params.get('ref'));
  if (!ref) return false;
  setStorageItem(REFERRAL_STORAGE_KEY, { code: ref, capturedAt: Date.now() });
  return true;
}

export function getStoredReferralCode() {
  const payload = getStorageItem(REFERRAL_STORAGE_KEY);
  if (!payload?.code) return null;
  const capturedAt = Number(payload.capturedAt) || 0;
  if (capturedAt && Date.now() - capturedAt > REFERRAL_TTL_MS) {
    removeStorageItem(REFERRAL_STORAGE_KEY);
    return null;
  }
  return normalizeReferralCode(payload.code);
}

export function clearStoredReferralCode() {
  removeStorageItem(REFERRAL_STORAGE_KEY);
}

export function buildReferralLink(referralCode, origin = window.location.origin) {
  const code = normalizeReferralCode(referralCode);
  if (!code) return '';
  const base = (origin || '').replace(/\/$/, '');
  return `${base}/auth?ref=${encodeURIComponent(code)}`;
}
