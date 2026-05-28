/**
 * SEO defaults and per-route metadata (title, description, robots).
 * Canonical site URL: set VITE_PUBLIC_SITE_URL in production (e.g. https://rsd-ai.ru).
 */

const FALLBACK_ORIGIN = 'https://rsd-ai.ru';

const DEFAULT_TITLE = 'RSD | Ваш персональный ИИ-агент для бизнеса за 5 минут';
const DEFAULT_DESCRIPTION =
  'RSD — no-code платформа для ИИ-агентов под поддержку, продажи и внутренние процессы. Соберите сценарий без разработчиков: ответы опираются на ваши документы и тон общения, который вы задаёте сами.';

export function getPublicSiteOrigin() {
  const fromEnv = import.meta.env.VITE_PUBLIC_SITE_URL?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/+$/, '');
  }
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    return window.location.origin;
  }
  return FALLBACK_ORIGIN;
}

const ROUTES = {
  '/': {
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
  },
  '/auth': {
    title: 'Вход и регистрация | RSD',
    description:
      'Войдите в RSD или создайте аккаунт, чтобы собирать ИИ-агентов на документах компании и подключать их к поддержке и продажам.',
  },
  '/pricing': {
    title: 'Цены на шаблоны агентов | RSD',
    description:
      'Цены RSD: ИИ консультант бесплатно, ИИ оператор и ИИ МОП — от 3 000 ₽/мес. Без разового взноса за запуск, токены LLM включены.',
  },
  '/documentation': {
    title: 'Документация | RSD',
    description:
      'Как настроить ИИ-агента в RSD: загрузка документов, сценарии, роли и ответы. Справка по возможностям no-code платформы.',
  },
  '/public-offer': {
    title: 'Публичная оферта | RSD',
    description: 'Публичная оферта на оказание услуг платформы RSD: условия, порядок оплаты и использования сервиса.',
  },
  '/user-agreement': {
    title: 'Пользовательское соглашение | RSD',
    description:
      'Пользовательское соглашение сервиса RSD: права и обязанности сторон, ограничения ответственности и правила использования.',
  },
  '/privacy': {
    title: 'Политика конфиденциальности | RSD',
    description:
      'Политика конфиденциальности RSD: какие данные обрабатываются, в каких целях и как обеспечивается защита персональной информации.',
  },
  '/management-portal': {
    title: 'Портал управления | RSD',
    description: 'Служебный раздел RSD.',
    robots: 'noindex, nofollow',
  },
};

const PRIVATE_PREFIXES = ['/agents', '/create-agent'];

export function getSeoForPath(pathname) {
  let path = pathname || '/';
  if (path.length > 1 && path.endsWith('/')) {
    path = path.slice(0, -1);
  }

  if (path.startsWith('/management-portal')) {
    return {
      title: ROUTES['/management-portal'].title,
      description: ROUTES['/management-portal'].description,
      robots: ROUTES['/management-portal'].robots,
    };
  }

  for (const prefix of PRIVATE_PREFIXES) {
    if (path === prefix || path.startsWith(`${prefix}/`)) {
      return {
        title: 'Личный кабинет | RSD',
        description: 'Раздел для авторизованных пользователей RSD.',
        robots: 'noindex, nofollow',
      };
    }
  }

  return ROUTES[path] || { title: DEFAULT_TITLE, description: DEFAULT_DESCRIPTION };
}

export const SEO_DEFAULT_TITLE = DEFAULT_TITLE;
export const SEO_DEFAULT_DESCRIPTION = DEFAULT_DESCRIPTION;
