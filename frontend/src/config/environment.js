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
const defaultBaseUrl = 'http://localhost:8000';

export const ENV_CONFIG = {
  isDevelopment,
  isProduction,

  // API Configuration — backend address used by Axios (apiClient.js)
  API: {
    BASE_URL: import.meta.env.VITE_API_BASE_URL || defaultBaseUrl,
    TIMEOUT: parseInt(import.meta.env.VITE_API_TIMEOUT || '30000', 10),
  },

  // App Configuration
  APP: {
    NAME: 'RSD',
    VERSION: import.meta.env.VITE_APP_VERSION || '1.0.0',
  },

  // Feature Flags
  FEATURES: {
    ENABLE_GOOGLE_AUTH: import.meta.env.VITE_ENABLE_GOOGLE_AUTH !== 'false',
    ENABLE_ANALYTICS: import.meta.env.VITE_ENABLE_ANALYTICS !== 'false',
  },

  // Storage Keys
  STORAGE_KEYS: {
    TOKEN: 'token',
    USER: 'user',
    THEME: 'theme',
  },
};

export default ENV_CONFIG;
