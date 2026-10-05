import { NAVIGATION_ROUTES } from '../../../config/constants';

export const UBT_MODULES = [
  { id: 'accounts', label: 'Менеджер аккаунтов' },
  { id: 'tasks', label: 'Задачи' },
  { id: 'stats', label: 'Моя статистика' },
  { id: 'neurocommenting', label: 'Нейрокомментинг' },
  { id: 'neurochatting', label: 'Нейрочаттинг' },
  { id: 'masslooking', label: 'Масслукинг' },
  { id: 'chat-broadcasts', label: 'Чат-рассылки' },
  { id: 'neuroshilling', label: 'Нейрошиллинг' },
  { id: 'masspriming', label: 'Масспрайминг' },
  { id: 'warmup', label: 'Прогрев аккаунтов' },
  { id: 'parser', label: 'Парсер' },
];

export const ubtModulePath = (automationId, moduleId) =>
  NAVIGATION_ROUTES.CUSTOM_AUTOMATION_UBT(automationId, moduleId);

export const moduleByPath = (pathname) => {
  const match = String(pathname || '').match(/\/ubt\/([^/]+)/);
  return match ? match[1] : null;
};
