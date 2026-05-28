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
  AUTH_GOOGLE: '/api/users/oauth/google',
  AUTH_REGISTER: '/api/users/registration',
  AUTH_REGISTER_RESEND_CODE: '/api/users/registration/resend-code',
  AUTH_REGISTER_VERIFY: '/api/users/registration/verify',
  AUTH_PASSWORD_RESET_REQUEST: '/api/users/password-reset/request',
  AUTH_PASSWORD_RESET_VERIFY: '/api/users/password-reset/verify',
  AUTH_PASSWORD_RESET_CONFIRM: '/api/users/password-reset/confirm',
  AUTH_LOGOUT: '/api/users/logout',
  AUTH_REFRESH: '/api/users/refresh',

  // Users
  USERS_ME: '/api/users/me',
  USERS_PROFILE: '/api/users/profile',
  USERS_TELEGRAM_LINK_START: '/api/users/telegram-link/start',
  USER_ERROR_REPORTS: '/api/users/error-reports',

  // Agents
  AGENTS_LIST: '/api/agents/allBy_tgID',
  AGENTS_CREATE_EMPTY: '/api/agents',
  AGENTS_CREATE: '/api/agents/by_token',
  AGENTS_CREATE_USERBOT: '/api/agents/by_userbot_session',
  AGENTS_USERBOT_REQUEST_CODE: '/api/agents/userbot/request_code',
  AGENTS_USERBOT_VERIFY_CODE: '/api/agents/userbot/verify_code',
  AGENTS_USERBOT_QR_START: '/api/agents/userbot/qr/start',
  AGENTS_USERBOT_QR_STATUS: '/api/agents/userbot/qr/status',
  AGENTS_USERBOT_QR_VERIFY_2FA: '/api/agents/userbot/qr/verify_2fa',
  AGENTS_USERBOT_IMPORT_SESSION: '/api/agents/userbot/import_session',
  AGENTS_WHATSAPP_USERBOT_REQUEST_CODE: '/api/agents/whatsapp_userbot/request_code',
  AGENTS_WHATSAPP_USERBOT_VERIFY_CODE: '/api/agents/whatsapp_userbot/verify_code',
  AGENTS_WHATSAPP_USERBOT_AUTH_STATUS: '/api/agents/whatsapp_userbot/auth_status',
  AGENTS_CHANNELS_LIST: '/api/agents/channels',
  AGENTS_CHANNELS_ADD_BOT: '/api/agents/channels/by_token',
  AGENTS_CHANNELS_ADD_USERBOT: '/api/agents/channels/by_userbot_session',
  AGENTS_CHANNELS_ADD_MAX_BOT: '/api/agents/channels/by_max_bot',
  AGENTS_CHANNELS_ADD_MAX_USERBOT: '/api/agents/channels/by_max_userbot',
  AGENTS_CHANNELS_ADD_WHATSAPP_USERBOT: '/api/agents/channels/by_whatsapp_userbot',
  AGENTS_CHANNELS_ADD_WHATSAPP_BUSINESS_API: '/api/agents/channels/by_whatsapp_business_api',
  AGENTS_CHANNELS_ADD_TELEPHONY: '/api/agents/channels/add-telephony',
  AGENTS_CHANNELS_VALIDATE_TELEPHONY: '/api/agents/channels/telephony/validate',
  AGENTS_CHANNELS_TELEPHONY_PLATFORM: '/api/agents/channels/telephony/platform',
  AGENTS_CHANNELS_DELETE: '/api/agents/channels',
  AGENTS_ANALYTICS_TELEPHONY_CALLS: '/api/agents/analytics/telephony/calls',
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
  AGENTS_ANALYTICS_TIMESERIES: '/api/agents/analytics/timeseries',
  AGENTS_ANALYTICS_CRM_ACTIONS: '/api/agents/analytics/crm_actions',
  AGENTS_ANALYTICS_FROZEN: '/api/agents/analytics/frozen',
  AGENTS_TELEGRAM_SEND_TO_USER: '/api/agents/telegram/send_to_user',
  AGENTS_EXTERNAL_SEND_TO_USER: '/api/agents/external/send_to_user',
  AGENTS_TELEGRAM_BROADCAST_RECIPIENTS: '/api/agents/telegram/broadcast_recipients',
  AGENTS_TELEGRAM_BROADCAST: '/api/agents/telegram/broadcast',
  AGENTS_WHATSAPP_USERBOT_SEND_TO_USER: '/api/agents/whatsapp_userbot/send_to_user',
  AGENTS_MAX_USERBOT_SEND_TO_USER: '/api/agents/max_userbot/send_to_user',
  AGENTS_WHATSAPP_USERBOT_BROADCAST_RECIPIENTS: '/api/agents/whatsapp_userbot/broadcast_recipients',
  AGENTS_WHATSAPP_USERBOT_BROADCAST: '/api/agents/whatsapp_userbot/broadcast',
  AGENTS_SALES_MANAGER_EXCEL_UPLOAD: '/api/agents/sales_manager/contacts/excel-upload',
  AGENTS_SALES_MANAGER_IMPORT_STATUS: '/api/agents/sales_manager/contacts/import-status',
  AGENTS_CRM_CONNECT: '/api/agents/crm/connect',
  AGENTS_CRM_VALIDATE: '/api/agents/crm/validate',
  AGENTS_CRM_HEALTH: '/api/agents/crm/health',
  AGENTS_ADMIN_TEMPLATE_STAFF: '/api/agents/admin_template/staff',
  AGENTS_ADMIN_TEMPLATE_SERVICES: '/api/agents/admin_template/services',
  AGENTS_ADMIN_TEMPLATE_RESOURCES: '/api/agents/admin_template/resources',
  AGENTS_ADMIN_TEMPLATE_SCHEDULE: '/api/agents/admin_template/schedule',
  AGENTS_ADMIN_TEMPLATE_SCHEDULE_AVAILABLE: '/api/agents/admin_template/schedule/available',
  AGENTS_ADMIN_TEMPLATE_APPOINTMENTS: '/api/agents/admin_template/appointments',
  AGENTS_ADMIN_TEMPLATE_APPOINTMENTS_RESCHEDULE: '/api/agents/admin_template/appointments/reschedule',
  AGENTS_ADMIN_TEMPLATE_APPOINTMENTS_CANCEL: '/api/agents/admin_template/appointments/cancel',
  AGENTS_ADMIN_TEMPLATE_APPOINTMENTS_CONFIRM: '/api/agents/admin_template/appointments/confirm',
  AGENTS_ADMIN_TEMPLATE_REFUND_REQUESTS: '/api/agents/admin_template/refund_requests',
  AGENTS_ADMIN_TEMPLATE_REFUND_REQUESTS_APPROVE: '/api/agents/admin_template/refund_requests/approve',
  AGENTS_ADMIN_TEMPLATE_REFUND_REQUESTS_REJECT: '/api/agents/admin_template/refund_requests/reject',
  AGENTS_ADMIN_TEMPLATE_OCCUPANCY: '/api/agents/admin_template/occupancy',
  AGENTS_ADMIN_TEMPLATE_WAITLIST: '/api/agents/admin_template/waitlist',
  AGENTS_ADMIN_TEMPLATE_CLIENT_PROFILES: '/api/agents/admin_template/client_profiles',
  AGENTS_ADMIN_TEMPLATE_QUICK_REPLIES: '/api/agents/admin_template/quick_replies',
  AGENTS_ADMIN_TEMPLATE_REMINDERS_RUN: '/api/agents/admin_template/reminders/run',
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
  ADMIN_CREATE_USER: '/api/admin/users',
  ADMIN_AGENTS: '/api/admin/agents',
  ADMIN_CHATS: '/api/admin/chats',
  ADMIN_TURNKEY_REQUESTS: '/api/admin/turnkey-requests',
  ADMIN_PLANS: '/api/admin/plans',
  ADMIN_PROMO_CODES: '/api/admin/promo-codes',
  ADMIN_BAN_USER: (userId) => `/api/admin/users/${userId}/ban`,
  ADMIN_UNBAN_USER: (userId) => `/api/admin/users/${userId}/unban`,
  ADMIN_GIFT_SUBSCRIPTION: (userId) => `/api/admin/users/${userId}/gift-subscription`,
  ADMIN_FREE_AGENT_ACTIVATION: (userId) => `/api/admin/users/${userId}/free-agent-activation`,
  ADMIN_DELETE_PROMO_CODE: (promoCodeId) => `/api/admin/promo-codes/${promoCodeId}`,
  ADMIN_ERROR_REPORTS: '/api/admin/error-reports',
  ADMIN_EMAIL_BROADCAST: '/api/admin/email-broadcast',
  ADMIN_EMAIL_TARGETED_PREVIEW: '/api/admin/email-targeted-preview',
  ADMIN_EMAIL_TARGETED_BROADCAST: '/api/admin/email-targeted-broadcast',
  ADMIN_EMAIL_TARGETED_JOB: (jobId) => `/api/admin/email-targeted-broadcast/jobs/${jobId}`,
  TURNKEY_REQUESTS: '/api/payments/turnkey-requests',

  // Article Publisher
  ADMIN_AP_SETTINGS: '/api/admin/article-publisher/settings',
  ADMIN_AP_TOPICS: '/api/admin/article-publisher/topics',
  ADMIN_AP_TOPICS_GENERATE: '/api/admin/article-publisher/topics/generate',
  ADMIN_AP_TOPIC_DELETE: (id) => `/api/admin/article-publisher/topics/${id}`,
  ADMIN_AP_IMAGES: '/api/admin/article-publisher/images',
  ADMIN_AP_IMAGE_DELETE: (id) => `/api/admin/article-publisher/images/${id}`,
  ADMIN_AP_IMAGE_FILE: (id) => `/api/admin/article-publisher/images/${id}/file`,
  ADMIN_AP_JOBS: '/api/admin/article-publisher/jobs',
  ADMIN_AP_RUN_NOW: '/api/admin/article-publisher/run-now',
  ADMIN_AP_PREVIEW: '/api/admin/article-publisher/preview-article',

  ADMIN_SALES_TEAM: '/api/admin/sales/team-members',
  ADMIN_SALES_FUNNEL: '/api/admin/sales/funnel',
  ADMIN_SALES_TEAM_MEMBER: (id) => `/api/admin/sales/team-members/${id}`,
  ADMIN_SALES_EXCEL_UPLOAD: '/api/admin/sales/contacts/excel-upload',
  ADMIN_SALES_CONTACT_MANUAL: '/api/admin/sales/contacts/manual',
  ADMIN_SALES_CRM_CLEAR: '/api/admin/sales/contacts/clear',

  SALES_LOGIN: '/api/sales/login',
  SALES_ME: '/api/sales/me',
  SALES_CONTACTS: '/api/sales/contacts',
  SALES_CONTACT: (id) => `/api/sales/contacts/${id}`,
  SALES_CONTACT_INVOICE: (id) => `/api/sales/contacts/${id}/invoice`,
  SALES_CONTACTS_REQUEST_MORE: '/api/sales/contacts/request-more',
  SALES_MGMT_TEAM: '/api/sales/management/team-members',
  SALES_MGMT_FUNNEL: '/api/sales/management/funnel',
  SALES_MGMT_TEAM_MEMBER: (id) => `/api/sales/management/team-members/${id}`,
  SALES_MGMT_EXCEL_UPLOAD: '/api/sales/management/contacts/excel-upload',
  SALES_MGMT_CRM_CLEAR: '/api/sales/management/contacts/clear',
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
  USERNAME_MAX_LENGTH_LOGIN: 255,   // LoginUser.name (username or email)
  USERNAME_MAX_LENGTH_REGISTER: 32, // NewUser.name
  PASSWORD_MIN_LENGTH: 6,          // both schemas
  PASSWORD_MAX_LENGTH: 30,          // both schemas
  EMAIL_CODE_LENGTH: 6,
  EMAIL_RESEND_COOLDOWN_SECONDS: 120,
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
