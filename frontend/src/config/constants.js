/**
 * Application constants
 * Defines static values used throughout the application
 */

export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  UNPROCESSABLE_ENTITY: 422,
  INTERNAL_SERVER_ERROR: 500,
  SERVICE_UNAVAILABLE: 503,
};

export const API_ROUTES = {
  // Auth (backend: prefix /api/users)
  AUTH_LOGIN: '/api/users/login',
  AUTH_REGISTER: '/api/users/registration',
  AUTH_LOGOUT: '/api/users/logout',
  AUTH_REFRESH: '/api/users/refresh',

  // Users
  USERS_ME: '/api/users/me',
  USERS_PROFILE: '/api/users/profile',
  USERS_TELEGRAM_LINK_START: '/api/users/telegram-link/start',

  // Agents
  AGENTS_LIST: '/api/agents/allBy_tgID',
  AGENTS_CREATE: '/api/agents/by_token',
  AGENTS_UPDATE: '/api/agents/by_botID',
  AGENTS_DELETE: '/api/agents',
  AGENTS_DETAIL: '/api/agents',
  AGENTS_TOGGLE: '/api/agents/toggle_status',
  AGENTS_AI_IMPROVE_PROMPT: '/api/agents/ai/improve_prompt',
  AGENTS_AI_GENERATE_WELCOME: '/api/agents/ai/generate_welcome',
  AGENTS_EXTERNAL_CHAT: '/api/agents/external/chat',
  AGENTS_REGENERATE_EXTERNAL_KEY: '/api/agents/external/regenerate_key',
  AGENTS_ANALYTICS_SUMMARY: '/api/agents/analytics/summary',
  AGENTS_ANALYTICS_CHATS: '/api/agents/analytics/chats',
  DOCUMENTS_CREATE: '/api/documents',
  DOCUMENTS_CREATE_LINK: '/api/documents/link',
  DOCUMENTS_LIST_BY_BOT: '/api/documents/allBy_botID',
  DOCUMENTS_DELETE: (docId) => `/api/documents/${docId}`,

  // Pricing
  PRICING_LIST: '/pricing',

  // Admin portal
  ADMIN_LOGIN: '/api/admin/login',
  ADMIN_STATS: '/api/admin/stats',
  ADMIN_USERS: '/api/admin/users',
  ADMIN_AGENTS: '/api/admin/agents',
  ADMIN_TURNKEY_REQUESTS: '/api/admin/turnkey-requests',
  ADMIN_PLANS: '/api/admin/plans',
  ADMIN_PROMO_CODES: '/api/admin/promo-codes',
  ADMIN_BAN_USER: (userId) => `/api/admin/users/${userId}/ban`,
  ADMIN_UNBAN_USER: (userId) => `/api/admin/users/${userId}/unban`,
  ADMIN_GIFT_SUBSCRIPTION: (userId) => `/api/admin/users/${userId}/gift-subscription`,
  ADMIN_DELETE_PROMO_CODE: (promoCodeId) => `/api/admin/promo-codes/${promoCodeId}`,
  TURNKEY_REQUESTS: '/api/payments/turnkey-requests',
};

export const AGENT_ROLES = {
  SALES_MANAGER: 'sales_manager',
  SUPPORT: 'support',
  ASSISTANT: 'assistant',
};

export const AGENT_TASKS = {
  SALES: 'sales',
  FAQ: 'faq',
  CONTACTS: 'contacts',
};

// Pricing plans are served by backend (/api/payments/plans) to keep bot + web consistent.
export const PRICING_PLANS = [];

export const NAVIGATION_ROUTES = {
  HOME: '/',
  AUTH: '/auth',
  AGENTS: '/agents',
  AGENT_ANALYTICS: (id) => `/agents/${id}/analytics`,
  CREATE_AGENT: '/create-agent',
  DOCUMENTATION: '/documentation',
  EDIT_AGENT: (id) => `/agents/${id}/edit`,
  PRICING: '/pricing',
  MANAGEMENT_PORTAL: '/management-portal',
  PUBLIC_OFFER: '/public-offer',
  USER_AGREEMENT: '/user-agreement',
  PRIVACY_POLICY: '/privacy',
};

// User-facing messages; backend detail (FastAPI) is preferred when present (see errorUtils).
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Ошибка подключения. Проверьте интернет соединение.',
  UNAUTHORIZED: 'Пожалуйста, войдите в систему.',
  FORBIDDEN: 'У вас нет доступа к этому ресурсу.',
  NOT_FOUND: 'Ресурс не найден.',
  CONFLICT: 'Пользователь уже существует.',
  SERVER_ERROR: 'Ошибка сервера. Попробуйте позже.',
  VALIDATION_ERROR: 'Пожалуйста, проверьте корректность данных.',
};

export const SUCCESS_MESSAGES = {
  AGENT_CREATED: 'Агент успешно создан!',
  AGENT_UPDATED: 'Агент успешно обновлен!',
  AGENT_DELETED: 'Агент успешно удален!',
  LOGIN_SUCCESS: 'Успешный вход в систему!',
  LOGOUT_SUCCESS: 'Вы успешно вышли из системы.',
};

export const VALIDATION = {
  EMAIL_PATTERN: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  // Auth: must match backend Pydantic (router_users/schemas.py)
  USERNAME_MIN_LENGTH: 3,
  USERNAME_MAX_LENGTH_LOGIN: 30,   // LoginUser.name
  USERNAME_MAX_LENGTH_REGISTER: 32, // NewUser.name
  PASSWORD_MIN_LENGTH: 6,          // both schemas
  PASSWORD_MAX_LENGTH: 30,          // both schemas
  AGENT_NAME_MIN_LENGTH: 2,
  AGENT_NAME_MAX_LENGTH: 50,
  FILE_MAX_SIZE: 10 * 1024 * 1024, // 10MB
  ALLOWED_FILE_EXTENSIONS: ['pdf', 'docx', 'doc', 'txt'],
};

export const DEBOUNCE_DELAY = {
  SEARCH: 300,
  RESIZE: 300,
  SCROLL: 300,
};

export default {
  HTTP_STATUS,
  API_ROUTES,
  AGENT_ROLES,
  AGENT_TASKS,
  PRICING_PLANS,
  NAVIGATION_ROUTES,
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
  VALIDATION,
  DEBOUNCE_DELAY,
};
