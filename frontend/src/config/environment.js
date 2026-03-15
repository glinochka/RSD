/**
 * Environment configuration
 * Centralizes all environment-specific settings
 */

const isDevelopment = import.meta.env.MODE === 'development';
const isProduction = import.meta.env.MODE === 'production';

export const ENV_CONFIG = {
  isDevelopment,
  isProduction,
  
  // API Configuration
  API: {
    BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    TIMEOUT: parseInt(import.meta.env.VITE_API_TIMEOUT || '30000'),
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
