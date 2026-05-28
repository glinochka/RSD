export const formatRubPrice = (value) => Number(value || 0).toLocaleString('ru-RU');

export const formatSetupPrice = (setupRubMin, { isFree = false } = {}) => {
  if (isFree || setupRubMin <= 0) return 'Бесплатно';
  return `от ${formatRubPrice(setupRubMin)} ₽`;
};

export const formatMaintenancePrice = (monthlyRubMin) => {
  if (monthlyRubMin <= 0) return null;
  return `от ${formatRubPrice(monthlyRubMin)} ₽/мес`;
};

export const getTemplateLabel = (code) => {
  const labels = {
    qa: 'ИИ консультант',
    crm_admin: 'ИИ оператор',
    sales_manager: 'ИИ МОП',
    content_factory: 'Контент‑завод',
    ai_logist: 'ИИ Логист',
    ai_manager: 'ИИ менеджер',
  };
  return labels[code] || code;
};

export const COMING_SOON_TEMPLATES = [
  {
    id: 'ai_logist',
    name: 'ИИ Логист',
    features: [
      'Статусы заказов и сроки доставки',
      'Ответы по маршрутам и складам',
      'Интеграция с WMS / ERP',
    ],
  },
  {
    id: 'content_factory',
    name: 'Контент‑завод',
    features: [
      'Генерация текстов и сценариев',
      'Видео и визуал под бренд',
      'Публикация в ваши каналы',
    ],
  },
  {
    id: 'ai_manager',
    name: 'ИИ менеджер',
    features: [
      'Входящие звонки и телефония',
      'Квалификация и запись клиентов',
      'Передача живому оператору',
    ],
  },
];

export const SPECIAL_CONDITIONS = [
  {
    id: 'white_label',
    name: 'White label сотрудничество',
    description: 'Запуск платформы под вашим брендом и доменом для агентств и интеграторов.',
    features: [
      'Ваш логотип и домен',
      'Кастомизация интерфейса',
      'Партнёрская модель и сопровождение',
    ],
    requestLabel: 'White label сотрудничество',
    modalTitle: 'Заявка на White label',
    requestPlaceholder: 'Опишите бренд, аудиторию и формат сотрудничества',
  },
  {
    id: 'freelancers',
    name: 'Для фрилансеров',
    description: 'Специальные условия на запуск агентов для независимых специалистов и небольших команд.',
    features: [
      'Скидки на ежемесячное обслуживание',
      'Гибкая оплата подписки',
      'Реферальная программа',
    ],
    requestLabel: 'Условия для фрилансеров',
    modalTitle: 'Заявка для фрилансеров',
    requestPlaceholder: 'Расскажите о проектах, объёме и нужных шаблонах',
  },
];

export const POLICY_NOTES = [
  'Оплата только ежемесячная — разовый взнос за запуск не требуется.',
  'Первый месяц после создания агента ежемесячное обслуживание бесплатно.',
  'Далее обслуживание — подписка на обновления и работу серверов (от 3 000 ₽/мес).',
  'Сложная ручная настройка и интеграции с CRM или ERP оцениваются отдельно.',
  'Токены LLM на текущем этапе включены — расходы на модели покрывает платформа.',
];

export const PRICING_PAGE_TEMPLATE_ORDER = ['qa', 'crm_admin', 'sales_manager'];

export default {
  formatRubPrice,
  formatSetupPrice,
  formatMaintenancePrice,
  getTemplateLabel,
  COMING_SOON_TEMPLATES,
  SPECIAL_CONDITIONS,
  POLICY_NOTES,
};
