export const JOB_PARAM_LABELS = {
  account_ids: 'Аккаунты',
  chat_ids: 'Каналы и чаты',
  folder_ids: 'Папки',
  channel_ids: 'Каналы',
  blacklisted_account_ids: 'Чёрный список аккаунтов',
  chat_assignments: 'Распределение по аккаунтам',
  reserve_chat_ids: 'Запасной пул',
  post_filter: 'Фильтр постов',
  keywords: 'Ключевые слова',
  probability: 'Вероятность, %',
  min_words: 'Минимальное количество слов',
  max_per_chat: 'Максимум на чат в день',
  max_per_account: 'Максимум действий на аккаунт в день',
  comment_delay_min: 'Пауза между действиями от',
  comment_delay_max: 'Пауза между действиями до',
  max_per_hour: 'Максимум в час',
  max_replies_per_run: 'Ответов за проход',
  delay_before_min: 'Пауза после поста от',
  delay_before_max: 'Пауза после поста до',
  join_delay_min: 'Пауза между вступлениями от',
  join_delay_max: 'Пауза между вступлениями до',
  delay_min: 'Задержка от',
  delay_max: 'Задержка до',
  delay_group_min: 'Пауза между чатами от',
  delay_group_max: 'Пауза между чатами до',
  delay_msg_min: 'Пауза между сообщениями от',
  delay_msg_max: 'Пауза между сообщениями до',
  delay_peer_min: 'Пауза между диалогами от',
  delay_peer_max: 'Пауза между диалогами до',
  delay_chat: 'Пауза между чатами',
  delay_user: 'Пауза между пользователями',
  respect_night_hours: 'Ночной простой',
  require_proxy: 'Только с прокси',
  hide_in_work: 'Скрывать аккаунты в работе',
  include_joined: 'Работать с текущими чатами/каналами',
  signature_enabled: 'Подпись под постом',
  avatar_from_profile: 'Аватар как у профиля',
  posts_per_day: 'Постов в день',
  prompt_id: 'Промпт',
  enabled: 'Модуль включён',
  only_joined: 'Только уже вступившие',
  reply_mode: 'Режим ответа',
  reply_condition: 'Условие ответа',
  work_mode: 'Режим работы',
  work_always: 'Работать без лимита',
  context_depth: 'Глубина контекста',
  chat_shilling: 'Шиллинг в чатах',
  post_shilling: 'Шиллинг под постами',
  unique_messages: 'Уникальные сообщения',
  skip_fresh: 'Пропускать свежие сообщения',
  view_feed: 'Смотреть ленту',
  stories_limit: 'Лимит историй',
  skip_seen: 'Пропускать уже просмотренные',
  skip_hours: 'Не повторять раньше, часов',
  limit_rate: 'Соблюдать лимиты',
  messages: 'Сообщения',
  first_mode: 'Первое сообщение',
  skip_errors: 'Пропускать ошибки',
  skip_sent: 'Не писать повторно',
  scenario: 'Сценарий',
  imitate_typing: 'Имитировать печать',
  warmup_slow: 'Медленный прогрев',
  max_messages: 'Максимум сообщений',
  errors_until_stop: 'Ошибок до остановки',
  weekdays: 'Дни недели',
  work_hour_start: 'Час начала',
  work_hour_end: 'Час окончания',
  end_at: 'Остановить в',
  source: 'Источник',
  targets: 'Цели',
  do_join: 'Вступать в чаты',
  joins_complete: 'Завершено ли вступление в чаты',
  since_hours: 'Сообщения за, часов',
  member_limit: 'Лимит участников',
  skip_bots: 'Пропускать ботов',
  skip_deleted: 'Пропускать удалённые',
  skip_scam: 'Пропускать скамеров',
  only_username: 'Только с username',
  only_photo: 'Только с фото',
  only_premium: 'Только Premium',
  only_admins: 'Только админы',
  only_active_stories: 'Только с активными историями',
  mode: 'Режим',
  intensity: 'Интенсивность',
  do_warmup_dms: 'Прогрев в ЛС',
  do_peer_dialogs: 'Диалоги между аккаунтами',
  do_reactions: 'Реакции',
  do_read_channels: 'Чтение каналов',
  do_stories: 'Истории',
  do_comment_contacts: 'Комментарии контактам',
  do_joins: 'Вступления',
  session_minutes: 'Длительность сессии, мин',
  recipients: 'Получатели',
  query: 'Запрос',
  max_chats: 'Максимум чатов',
  require_approval: 'Нужно одобрение',
  relevance_threshold: 'Порог релевантности',
};

export const JOB_RESULT_LABELS = {
  status: 'Статус',
  sent: 'Отправлено',
  shilled: 'Шиллинг',
  joined: 'Вступлений',
  folders: 'Папок',
  chats_processed: 'Чатов обработано',
  comments_sent: 'Комментариев',
  replies_sent: 'Ответов',
  dialogues_sent: 'Диалогов',
  viewed: 'Просмотров',
  parsed: 'Собрано',
  errors: 'Ошибки',
  skipped: 'Пропущено',
  reason: 'Причина',
  items: 'Элементы',
};

export const paramLabel = (key) => JOB_PARAM_LABELS[key] || key;
export const resultLabel = (key) => JOB_RESULT_LABELS[key] || key;

const MINUTE_KEYS = new Set([
  'join_delay_min',
  'join_delay_max',
  'comment_delay_min',
  'comment_delay_max',
  'delay_before_min',
  'delay_before_max',
]);

const SECOND_KEYS = new Set([
  'delay_min',
  'delay_max',
  'delay_group_min',
  'delay_group_max',
  'delay_msg_min',
  'delay_msg_max',
  'delay_peer_min',
  'delay_peer_max',
  'delay_chat',
  'delay_user',
]);

const CHOICES = {
  post_filter: [
    { value: 'new', label: 'Новые посты' },
    { value: 'keywords', label: 'По ключевым словам' },
  ],
  reply_mode: [
    { value: 'interval', label: 'По интервалу' },
    { value: 'triggers', label: 'На триггеры' },
  ],
  work_mode: [
    { value: 'count', label: 'По количеству' },
    { value: 'time', label: 'По времени' },
  ],
  first_mode: [
    { value: 'template', label: 'Мой текст' },
    { value: 'ai', label: 'ИИ' },
  ],
  mode: [
    { value: 'auto', label: 'Авто' },
    { value: 'manual', label: 'Ручной' },
    { value: 'monitoring', label: 'Мониторинг' },
  ],
  intensity: [
    { value: 'auto', label: 'Авто' },
    { value: 'cautious', label: 'Осторожный' },
    { value: 'normal', label: 'Нормальный' },
    { value: 'trusted', label: 'Доверенный' },
  ],
  source: [
    { value: 'messages', label: 'По сообщениям' },
    { value: 'participants', label: 'Участники' },
    { value: 'comments', label: 'По комментариям' },
  ],
  scenario: [
    { value: 'loop', label: 'По кругу' },
    { value: 'once', label: 'Один раз' },
  ],
  content_mode: [
    { value: 'write', label: 'Свои тексты' },
    { value: 'mirror', label: 'Чужой канал' },
  ],
  ttl_mode: [
    { value: 'toggle', label: 'Как в настройке' },
    { value: 'enable', label: 'Включить TTL' },
    { value: 'disable', label: 'Выключить TTL' },
  ],
};

const BOOL_OPTIONS = [
  { value: 'Да', label: 'Да' },
  { value: 'Нет', label: 'Нет' },
];

export const minutesFromSeconds = (seconds) => {
  const amount = Number(seconds);
  if (!Number.isFinite(amount) || amount <= 0) {
    return 0;
  }
  return Math.max(1, Math.round(amount / 60));
};

export const fieldKind = (key, value) => {
  if (typeof value === 'boolean') {
    return 'bool';
  }
  if (CHOICES[key]) {
    return 'choice';
  }
  if (MINUTE_KEYS.has(key)) {
    return 'minutes';
  }
  if (SECOND_KEYS.has(key)) {
    return 'seconds';
  }
  if (typeof value === 'number') {
    return 'number';
  }
  if (typeof value === 'string' && value.length > 80) {
    return 'long';
  }
  return 'text';
};

export const choiceOptions = (key, current) => {
  if (fieldKind(key, current) === 'bool' || typeof current === 'boolean') {
    return BOOL_OPTIONS;
  }
  const base = CHOICES[key];
  if (!base) {
    return null;
  }
  const value = current === null || current === undefined ? '' : String(current);
  if (value && !base.some((item) => item.value === value)) {
    return [...base, { value, label: value }];
  }
  return base;
};

const choiceLabel = (key, value) => {
  const options = choiceOptions(key, value);
  const found = options?.find((item) => item.value === String(value));
  return found ? found.label : String(value ?? '');
};

export const displayParam = (key, value) => {
  if (typeof value === 'boolean') {
    return value ? 'Да' : 'Нет';
  }
  if (CHOICES[key]) {
    return choiceLabel(key, value);
  }
  if (MINUTE_KEYS.has(key) && Number.isFinite(Number(value))) {
    return `${minutesFromSeconds(value)} мин`;
  }
  if (SECOND_KEYS.has(key) && Number.isFinite(Number(value))) {
    return `${Math.max(0, Math.round(Number(value)))} сек`;
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join(', ');
  }
  if (value && typeof value === 'object') {
    return '';
  }
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
};

export const editParam = (key, value) => {
  const kind = fieldKind(key, value);
  if (kind === 'bool') {
    return value ? 'Да' : 'Нет';
  }
  if (kind === 'minutes') {
    return String(minutesFromSeconds(value));
  }
  if (kind === 'seconds' || kind === 'number') {
    return String(value ?? '');
  }
  if (kind === 'choice') {
    return String(value ?? '');
  }
  return value === null || value === undefined ? '' : String(value);
};

export const commitParam = (key, edited, original) => {
  const kind = fieldKind(key, original);
  if (kind === 'bool') {
    return edited === true || edited === 'Да' || edited === 'true' || edited === '1';
  }
  if (kind === 'minutes') {
    const shown = minutesFromSeconds(original);
    const next = Math.max(0, Math.round(Number(edited)));
    if (!Number.isFinite(next)) {
      return original;
    }
    if (next === shown) {
      return original;
    }
    return next * 60;
  }
  if (kind === 'seconds' || kind === 'number') {
    const next = Number(edited);
    if (!Number.isFinite(next)) {
      return original;
    }
    return next;
  }
  if (kind === 'choice') {
    return String(edited ?? '');
  }
  return edited;
};
