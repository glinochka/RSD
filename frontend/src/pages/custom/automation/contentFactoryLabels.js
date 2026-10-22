export const CF_PLATFORMS = [
  {
    id: 'youtube',
    title: 'YouTube Shorts',
    hint: 'Основной канал для коротких роликов. Можно вставить refresh-токен или пройти OAuth.',
  },
  {
    id: 'instagram',
    title: 'Instagram Reels',
    hint: 'Видео уходит в Reels. Фото-карусель публикуется в ленту: в Reels листание кадров не поддерживается.',
  },
  {
    id: 'tiktok',
    title: 'TikTok',
    hint: 'Content Posting API: access token. Без него завод собирает ролик, но не публикует.',
  },
  {
    id: 'pinterest',
    title: 'Pinterest',
    hint: 'access token и board_id для Idea Pin / видеопина.',
  },
];

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
  { value: 'expert_friendly', label: 'Эксперт, по-человечески' },
  { value: 'bold', label: 'Дерзкий' },
  { value: 'calm', label: 'Спокойный' },
  { value: 'sales', label: 'Продающий' },
];

export const CF_ASPECTS = [
  { value: '9:16', label: '9:16 — Shorts / Reels / TikTok' },
  { value: '16:9', label: '16:9 — горизонталь YouTube' },
  { value: '1:1', label: '1:1 — квадрат' },
];

export const CF_VIDEO_MODELS = [
  { value: 'kling', label: 'Kling' },
  { value: 'runway', label: 'Runway' },
  { value: 'luma', label: 'Luma' },
  { value: 'preview', label: 'Только раскадровка' },
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
  youtube: 'refresh token или access token',
  instagram: 'access token и Instagram User ID',
  tiktok: 'access token Content Posting API',
  pinterest: 'access token и board_id',
};

export const IN_FLIGHT_STATUSES = ['queued', 'ideating', 'scripting', 'rendering', 'uniqualizing', 'ready', 'posting'];
