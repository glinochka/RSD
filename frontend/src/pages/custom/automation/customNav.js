import { NAVIGATION_ROUTES } from '../../../config/constants';

export const UBT_MODULES = [
  { id: 'accounts', label: 'Менеджер аккаунтов' },
  { id: 'tasks', label: 'Задачи' },
  { id: 'stats', label: 'Моя статистика' },
  { id: 'neurocommenting', label: 'Нейрокомментинг' },
  { id: 'neurochatting', label: 'Нейрочаттинг' },
  { id: 'masslooking', label: 'Масслукинг' },
  { id: 'chat-broadcasts', label: 'Чат-рассылки' },
  { id: 'dm-broadcasts', label: 'ЛС-рассылки' },
  { id: 'neuroshilling', label: 'Нейрошиллинг' },
  { id: 'masspriming', label: 'Масспрайминг' },
  { id: 'warmup', label: 'Прогрев аккаунтов' },
  { id: 'parser', label: 'Парсер юзеров' },
  { id: 'chats', label: 'Чаты и каналы' },
];

export const ubtModulePath = (automationId, moduleId) =>
  NAVIGATION_ROUTES.CUSTOM_AUTOMATION_UBT(automationId, moduleId);

export const folderOptions = (folders, emptyLabel = 'Все папки') => [
  { value: '', label: emptyLabel },
  ...(folders || []).map((folder) => ({ value: String(folder.id), label: folder.name })),
];

export const toggleNumericId = (ids, id) => {
  const list = Array.isArray(ids) ? ids : [];
  return list.includes(id) ? list.filter((item) => item !== id) : [...list, id];
};

export const moduleByPath = (pathname) => {
  const match = String(pathname || '').match(/\/ubt\/([^/]+)/);
  return match ? match[1] : null;
};

export const matchesPreset = (settings, preset) => (
  Boolean(settings && preset)
  && Object.entries(preset).every(([key, value]) => Number(settings[key]) === Number(value))
);
