/**
 * JWT access token helpers.
 * Tokens are stored via useLocalStorage/setStorageItem (JSON.stringify),
 * so always read with getStorageItem — never raw localStorage.getItem.
 */
import { ENV_CONFIG } from '../config/environment';
import { getStorageItem } from './storage';

const TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.TOKEN;

/**
 * @returns {string | null} Raw JWT access token
 */
export function getAccessToken() {
  const token = getStorageItem(TOKEN_KEY);
  if (typeof token !== 'string' || !token.trim()) {
    return null;
  }
  return token.trim();
}

/**
 * @returns {Record<string, string>} Authorization header or empty object
 */
export function getAuthHeaders() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
