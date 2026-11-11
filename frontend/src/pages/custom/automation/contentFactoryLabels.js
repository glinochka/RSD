export const CF_PLATFORMS = [
  {
    id: 'youtube',
    title: 'YouTube Shorts',
    hint: 'OAuth, refresh или access. Cookie и пароль Data API не принимает.',
  },
  {
    id: 'instagram',
    title: 'Instagram Reels',
    hint: 'Access token и Instagram User ID. Видео уходит в Reels, фото-карусель — в ленту.',
  },
  {
    id: 'tiktok',
    title: 'TikTok',
    hint: 'Уже выданный access token. Refresh можно сохранить, без ключей приложения он access не обновит.',
  },
  {
    id: 'pinterest',
    title: 'Pinterest',
    hint: 'Access token и board_id. Фото и карусель уходят пином. Видео по ссылке API не принимает.',
  },
  {
    id: 'vk',
    title: 'VK Клипы',
    hint: 'Пользовательский access token и id сообщества. Карусель собирается в слайд-шоу.',
  },
];

export const CF_LOGIN = {
  youtube: {
    note: 'Живые способы: OAuth, refresh token или access token. Пароль и cookie браузера не сохраняются.',
    refresh: true,
    access: true,
  },
  instagram: {
    note: 'Живой способ: access token и Instagram User ID. Отдельный refresh площадка здесь не отдаёт. Cookie сессии Graph не принимает.',
    refresh: false,
    access: true,
  },
  tiktok: {
    note: 'Живой способ: уже выданный access token. Если TikTok отдал refresh, его можно вставить: без ключей приложения он access не обновит.',
    refresh: true,
    access: true,
  },
  pinterest: {
    note: 'Живой способ: access token и board_id. Refresh сохраняется, если он есть, и сам access не крутит.',
    refresh: true,
    access: true,
  },
  vk: {
    note: 'Живой способ: пользовательский access token и id сообщества. Refresh VK ID можно сохранить, без ключей приложения он не крутит access.',
    refresh: true,
    access: true,
  },
};

export const CF_FORMATS = [
  { id: 'educational', label: 'Обучающее' },
  { id: 'direct_ad', label: 'Прямая реклама' },
  { id: 'storytelling', label: 'Сторителлинг' },
  { id: 'motion', label: 'Моушн' },
  { id: 'ugc', label: 'UGC' },
  { id: 'mixed', label: 'Микс' },
];

export const CF_STYLES = [
  { id: 'realism', label: 'Реализм' },
  { id: 'animation', label: 'Анимация' },
  { id: 'motion', label: 'Моушн' },
  { id: 'mixed', label: 'Микс' },
];

export const CF_TONES = [
  { value: 'expert_friendly', label: 'Свой из ниши' },
  { value: 'bold', label: 'Жёсткий, можно мат' },
  { value: 'satire', label: 'Сатира на новость' },
  { value: 'calm', label: 'Сухо по фактам' },
  { value: 'sales', label: 'Продажа через наблюдение' },
];

export const CF_ASPECTS = [
  { value: '9:16', label: '9:16 — Shorts / Reels / TikTok / VK Клипы' },
  { value: '16:9', label: '16:9 — горизонталь YouTube' },
  { value: '1:1', label: '1:1 — квадрат' },
];

export const CF_VIDEO_MODELS = [
  { value: 'kling', label: 'Kling' },
  { value: 'preview', label: 'Только раскадровка' },
  { value: 'runway', label: 'Runway — пока только раскадровка' },
  { value: 'luma', label: 'Luma — пока только раскадровка' },
];

export const CF_STATUS = {
  queued: 'В очереди',
  ideating: 'Идея',
  scripting: 'Сценарий',
  rendering: 'Генерация',
  uniqualizing: 'Уникализация',
  ready: 'Готов к посту',
  posting: 'Публикация',
  posted: 'Опубликован',
  failed: 'Ошибка',
  skipped: 'Пропущен',
  pending: 'Ждёт',
  processing: 'Обработка на площадке',
  held: 'Отложен',
  sandbox: 'Песочница',
  warming: 'Прогрев',
  connected: 'Подключён',
  ready_account: 'Готов',
  paused: 'Пауза',
  restricted: 'Ограничен',
  shadow_risk: 'Риск бана',
  disconnected: 'Отключён',
};

export const accountStatusLabel = (status) => {
  if (status === 'ready') {
    return 'Готов';
  }
  return CF_STATUS[status] || status || '—';
};

export const formatWhen = (value) => {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const money = (value) => {
  const amount = Number(value || 0);
  return `$${amount.toFixed(amount >= 1 ? 2 : 4)}`;
};

export const toggleChip = (list, id) => {
  const current = Array.isArray(list) ? list : [];
  return current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
};

export const CF_VIDEO_FILTERS = [
  { id: '', label: 'Все' },
  { id: 'queued', label: 'Очередь' },
  { id: 'rendering', label: 'Генерация' },
  { id: 'ready', label: 'Готовы' },
  { id: 'posted', label: 'Опубликованы' },
  { id: 'sandbox', label: 'Песочница' },
  { id: 'failed', label: 'Ошибки' },
  { id: 'skipped', label: 'Пропущены' },
];

export const CF_CREDENTIAL_FIELDS = {
  youtube: 'OAuth, refresh или access. Один access без refresh на строке виден отдельно',
  instagram: 'access token и Instagram User ID. Refresh эта площадка в подключении не отдаёт',
  tiktok: 'access token. Refresh сохраняется, но без ключей приложения access не обновляет',
  pinterest: 'access token и board_id. Refresh сохраняется, но сам access не крутит',
  vk: 'пользовательский access token и id сообщества. Refresh сохраняется, если VK его отдал',
};

export const CF_MUSIC_MODES = [
  { value: 'voice_bed', label: 'Голос и подложка' },
  { value: 'voice', label: 'Только голос' },
  { value: 'bed', label: 'Только подложка' },
  { value: 'off', label: 'Без музыки' },
];

export const IN_FLIGHT_STATUSES = ['queued', 'ideating', 'scripting', 'rendering', 'uniqualizing', 'ready', 'posting'];
