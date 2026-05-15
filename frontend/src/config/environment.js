/**
 * Environment configuration
 * Centralizes all environment-specific settings.
 *
 * API.BASE_URL must point to the backend server (default port 8000).
 * The frontend origin (this app's URL, e.g. http://localhost:3000) must be
 * whitelisted in the backend's CORS origins (see backend/app/origins.py).
 */

const isDevelopment = import.meta.env.MODE === 'development';
const isProduction = import.meta.env.MODE === 'production';

// Backend runs on port 8000 (server.py). Override with VITE_API_BASE_URL for LAN/production.
// API_ROUTES in constants.js already start with `/api/...`, so a base ending with `/api`
// would produce duplicated URLs (`/api/api/...`). Normalize that suffix away.
const defaultBaseUrl = 'http://localhost:8000';
const viteApiBase = import.meta.env.VITE_API_BASE_URL;

const normalizeApiBaseUrl = (rawBaseUrl) => {
  if (rawBaseUrl === undefined || rawBaseUrl === null) {
    return defaultBaseUrl;
  }
  const trimmed = String(rawBaseUrl).trim();
  if (trimmed === '') {
    return '';
  }

  // Keep same-origin mode safe even if env was set to `/api`.
  if (trimmed === '/api') {
    return '';
  }

  // Remove trailing slash and optional `/api` suffix (e.g. https://api.site.com/api).
  const noTrailingSlash = trimmed.replace(/\/+$/, '');
  return noTrailingSlash.replace(/\/api$/, '');
};

const resolvedApiBaseUrl = normalizeApiBaseUrl(viteApiBase);

export const ENV_CONFIG = {
  isDevelopment,
  isProduction,

  // API Configuration — backend address used by Axios (apiClient.js)
  API: {
    BASE_URL: resolvedApiBaseUrl,
    TIMEOUT: parseInt(import.meta.env.VITE_API_TIMEOUT || '30000', 10),
  },

  // App Configuration
  APP: {
    NAME: 'RSD',
    VERSION: import.meta.env.VITE_APP_VERSION || '1.0.0',
    GOOGLE_CLIENT_ID: import.meta.env.VITE_GOOGLE_CLIENT_ID || '',
  },

  // Feature Flags
  FEATURES: {
    ENABLE_GOOGLE_AUTH: import.meta.env.VITE_ENABLE_GOOGLE_AUTH !== 'false',
    ENABLE_ANALYTICS: import.meta.env.VITE_ENABLE_ANALYTICS !== 'false',
  },

  // Storage Keys
  STORAGE_KEYS: {
    TOKEN: 'token',
    REFRESH_TOKEN: 'refresh_token',
    USER: 'user',
    ADMIN_TOKEN: 'admin_token',
    SALES_TOKEN: 'sales_token',
    THEME: 'theme',
  },
};

export default ENV_CONFIG;
