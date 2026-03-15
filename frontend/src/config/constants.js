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
  // Auth
  AUTH_LOGIN: '/auth/login',
  AUTH_REGISTER: '/auth/register',
  AUTH_LOGOUT: '/auth/logout',
  AUTH_REFRESH: '/auth/refresh',

  // Users
  USERS_ME: '/users/me',
  USERS_PROFILE: '/users/profile',

  // Agents
  AGENTS_LIST: '/agents',
  AGENTS_CREATE: '/agents',
  AGENTS_UPDATE: (id) => `/agents/${id}`,
  AGENTS_DELETE: (id) => `/agents/${id}`,
  AGENTS_DETAIL: (id) => `/agents/${id}`,

  // Pricing
  PRICING_LIST: '/pricing',
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

export const PRICING_PLANS = [
  {
    id: 'basic',
    name: 'Базовая',
    price: 2990,
    currency: 'р',
    period: 'месяц',
    per: 'за агента',
    features: [
      '5 гб базы знаний',
      'tg-bot',
      'базовая аналитика',
    ],
  },
  {
    id: 'advanced',
    name: 'Продвинутая',
    price: 7990,
    currency: 'р',
    period: 'месяц',
    per: 'за агента',
    features: [
      '15 гб базы знаний',
      'tg-bot',
      'API',
    ],
  },
  {
    id: 'pro',
    name: 'Про',
    price: 14990,
    currency: 'р',
    period: 'месяц',
    per: 'за агента',
    features: [
      '50 гб базы знаний',
      'tg-bot',
      'API',
    ],
  },
];

export const NAVIGATION_ROUTES = {
  HOME: '/',
  AUTH: '/auth',
  AGENTS: '/agents',
  CREATE_AGENT: '/create-agent',
  EDIT_AGENT: (id) => `/agents/${id}/edit`,
  PRICING: '/pricing',
};

export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Ошибка подключения. Проверьте интернет соединение.',
  UNAUTHORIZED: 'Пожалуйста, войдите в систему.',
  FORBIDDEN: 'У вас нет доступа к этому ресурсу.',
  NOT_FOUND: 'Ресурс не найден.',
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
  PASSWORD_MIN_LENGTH: 8,
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
