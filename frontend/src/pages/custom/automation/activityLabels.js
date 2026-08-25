export const ACTIVITY_MODULE_TOGGLES = [
  { name: 'is_chat_monitoring_enabled', label: 'Перехват заявок' },
  { name: 'is_neurocommenting_enabled', label: 'Нейрокомментинг' },
  { name: 'is_shilling_enabled', label: 'Шиллинг' },
  { name: 'is_digital_footprint_enabled', label: 'Искусственная активность в чатах' },
  { name: 'is_dmp_one_enabled', label: 'DMP.one' },
  { name: 'is_amocrm_enabled', label: 'AmoCRM' },
];

export const CHAT_MODE_OPTIONS = [
  { value: 'monitoring', label: 'Перехват заявок' },
  { value: 'neurocommenting', label: 'Нейрокомментинг' },
  { value: 'discussion', label: 'Искусственная активность в чатах' },
  { value: 'shilling', label: 'Шиллинг' },
  { value: 'inactive', label: 'Неактивен' },
];

export const CHAT_MODE_OPTIONS_WITHOUT_INACTIVE = CHAT_MODE_OPTIONS.filter(
  (option) => option.value !== 'inactive',
);

export const ACTION_LABELS = {
  neurocommenting: 'Нейрокомментинг',
  discussion: 'Искусственная активность в чатах',
  dm: 'ЛС',
  chat_monitoring: 'Перехват заявок',
  dmp_outreach: 'DMP прогрев',
  lead_warmup: 'Прогрев лида',
  lead_delivery: 'Передача МОПу',
  shilling_chat: 'Шиллинг в чате',
  shilling_post: 'Шиллинг под постом',
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
  shilling: 'Шиллинг',
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
  shilling: ['industry', 'client_name', 'chat_title', 'post_text'],
};
