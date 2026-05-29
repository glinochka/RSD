export const formatRubPrice = (value) => Number(value || 0).toLocaleString('ru-RU');

export const formatSetupPrice = (setupRubMin, { isFree = false } = {}) => {
  if (isFree || setupRubMin <= 0) return 'Бесплатно';
  return `от ${formatRubPrice(setupRubMin)} ₽`;
};

export const formatMaintenancePrice = (monthlyRubMin) => {
  if (monthlyRubMin <= 0) return null;
  return `${formatRubPrice(monthlyRubMin)} ₽/мес`;
};

export const AGENT_CONTRACT_DURATION_OPTIONS = [
  { months: 1, label: '1 месяц', discountPercent: 0 },
  { months: 3, label: '3 месяца', discountPercent: 15 },
  { months: 6, label: '6 месяцев', discountPercent: 25 },
];

const roundToPriceEndingNinety = (value) => {
  const normalized = Number(value || 0);
  if (normalized <= 0) return 0;
  return Math.max(90, Math.round((normalized - 90) / 100) * 100 + 90);
};

export const calculateContractTotalRub = (monthlyPrice, months) => {
  const price = Number(monthlyPrice || 0);
  const option = AGENT_CONTRACT_DURATION_OPTIONS.find((row) => row.months === months)
    || AGENT_CONTRACT_DURATION_OPTIONS[0];
  const baseTotal = price * option.months;
  const discounted = Math.round(baseTotal * (1 - option.discountPercent / 100));
  return roundToPriceEndingNinety(discounted);
};

export const getTemplateLabel = (code) => {
  const labels = {
    qa: 'ИИ консультант',
    crm_admin: 'ИИ Администратор',
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
  'ИИ консультант — бесплатно.',
  'ИИ Администратор — 990 ₽/мес, ИИ МОП — 1 990 ₽/мес.',
  'Первые 3 дня после создания платного агента — бесплатный пробный период.',
  'Оплата на 1, 3 или 6 месяцев; при длительном сроке действует скидка.',
  'Токены LLM включены — расходы на модели покрывает платформа.',
];

export const PRICING_PAGE_TEMPLATE_ORDER = ['qa', 'crm_admin', 'sales_manager'];

export default {
  formatRubPrice,
  formatSetupPrice,
  formatMaintenancePrice,
  calculateContractTotalRub,
  AGENT_CONTRACT_DURATION_OPTIONS,
  getTemplateLabel,
  COMING_SOON_TEMPLATES,
  SPECIAL_CONDITIONS,
  POLICY_NOTES,
};
