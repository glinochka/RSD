export const ACTIVITY_MODULE_TOGGLES = [
  { name: 'is_chat_monitoring_enabled', label: 'Перехват заявок' },
  { name: 'is_neurocommenting_enabled', label: 'Нейрокомментинг' },
  { name: 'is_shilling_enabled', label: 'Шиллинг' },
  { name: 'is_digital_footprint_enabled', label: 'Искусственная активность в чатах' },
  { name: 'is_dmp_one_enabled', label: 'DMP.one' },
  { name: 'is_amocrm_enabled', label: 'AmoCRM' },
];

export const CHAT_TYPE_LABELS = {
  channel: 'Канал',
  broadcast: 'Канал',
  chat: 'Чат',
  group: 'Чат',
  supergroup: 'Чат',
  megagroup: 'Чат',
};

export const ACTION_LABELS = {
  chat_monitoring: 'Перехват заявок',
  neurocommenting: 'Нейрокомментинг',
  shilling: 'Шиллинг',
  discussion: 'Искусственная активность',
  dmp: 'Отписка в DMP',
  unsubscribe: 'Отписка',
  amocrm_transfer: 'Лид ушёл в Amo',
};

export const ACTIVITY_FEED_FILTERS = [
  { value: '', label: 'Все типы' },
  { value: 'neurocommenting', label: 'Нейрокомментинг' },
  { value: 'chat_monitoring', label: 'Перехват заявок' },
  { value: 'shilling', label: 'Шиллинг' },
  { value: 'discussion', label: 'Искусственная активность' },
  { value: 'dmp', label: 'Отписка в DMP' },
];

export const ACTIVITY_FEED_SORT = [
  { value: 'newest', label: 'Сначала новые' },
  { value: 'oldest', label: 'Сначала старые' },
];

export const DASHBOARD_ACTIVITY_KEYS = [
  'chat_monitoring',
  'neurocommenting',
  'shilling',
  'unsubscribe',
  'amocrm_transfer',
];

export const DASHBOARD_ACTIVITY_GROUP = {
  dm: 'chat_monitoring',
  chat_monitoring: 'chat_monitoring',
  neurocommenting: 'neurocommenting',
  shilling: 'shilling',
  shilling_chat: 'shilling',
  shilling_post: 'shilling',
  unsubscribe: 'unsubscribe',
  amocrm_transfer: 'amocrm_transfer',
};

export const PROMPT_TYPE_LABELS = {
  chat_monitoring_trigger: 'Перехват заявок: триггер',
  chat_monitoring_response: 'Перехват заявок: ответ',
  neurocommenting: 'Нейрокомментинг',
  discussion_reply: 'Искусственная активность в чатах',
  dmp_outreach: 'DMP: первое сообщение',
  lead_qualification: 'Квалификация лида',
  chat_relevance: 'Релевантность чата',
  profile_bio: 'Профиль bio',
  shilling: 'Шиллинг: вопрос и ответ',
  inbound_dm: 'Входящее ЛС',
};

export const SOLUTION_KIND_LABELS = {
  seo_saas: 'SEO SaaS',
  fulfillment: 'Фулфилмент',
  dmp_bot: 'DMP-бот',
  generic: 'Произвольное',
};

export const SOLUTION_KIND_OPTIONS = [
  { value: 'generic', label: 'Произвольное' },
  { value: 'seo_saas', label: 'SEO SaaS' },
  { value: 'fulfillment', label: 'Фулфилмент' },
  { value: 'dmp_bot', label: 'DMP-бот' },
];

export const VARIABLE_HINTS = {
  chat_monitoring_trigger: ['text'],
  chat_monitoring_response: ['text'],
  neurocommenting: ['post_text', 'chat_title'],
  discussion_reply: ['message_text', 'chat_title'],
  dmp_outreach: ['name', 'company', 'website', 'page', 'partner_utm_url', 'partner_promo_code', 'registered'],
  lead_qualification: ['history', 'last_incoming', 'partner_utm_url', 'partner_promo_code'],
  chat_relevance: ['query', 'title', 'description', 'chat_type', 'participants_count'],
  profile_bio: ['industry', 'name'],
  shilling: [],
  inbound_dm: ['incoming', 'product_context', 'partner_utm_url', 'partner_promo_code'],
};

export const ACCOUNT_ROLE_OPTIONS = [
  { value: 'neurocommenting', label: 'Нейрокомментинг' },
  { value: 'lead_intercept', label: 'Перехват заявок' },
  { value: 'shilling', label: 'Шиллинг' },
  { value: 'dmp', label: 'DMP' },
];

export const ACCOUNT_ROLE_LABELS = {
  neurocommenting: 'Нейрокомментинг',
  lead_intercept: 'Перехват заявок',
  shilling: 'Шиллинг',
  dmp: 'DMP',
};

export const WARMUP_STATUS_LABELS = {
  idle: 'Без прогрева',
  rest: 'Прогрев: день отдыха',
  warming: 'Прогрев: диалог',
  complete: 'Прогрев завершён',
};

export const parseShillingContent = (content) => {
  try {
    const data = JSON.parse(content || '');
    if (data && typeof data === 'object') {
      return {
        setup: data.setup || data.question || '',
        reply: data.reply || data.answer || '',
      };
    }
  } catch {
    // plain text is not a shilling pair
  }
  return { setup: '', reply: '' };
};
