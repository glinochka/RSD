/**
 * Default content templates for new blocks in the constructor.
 */

export const BLOCK_TYPE_META = {
  hero: {
    label: 'Главный экран',
    icon: 'hero',
    description: 'Заголовок, подзаголовок и кнопка',
  },
  services: {
    label: 'Услуги',
    icon: 'services',
    description: 'Сетка карточек услуг',
  },
  about: {
    label: 'О компании',
    icon: 'about',
    description: 'Текст и изображение',
  },
  contacts: {
    label: 'Контакты',
    icon: 'contacts',
    description: 'Контактная информация и форма',
  },
  cta: {
    label: 'Призыв к действию',
    icon: 'cta',
    description: 'Блок с кнопкой',
  },
  footer: {
    label: 'Подвал',
    icon: 'footer',
    description: 'Копирайт и ссылки',
  },
  'agent-widget': {
    label: 'Виджет агента',
    icon: 'contacts',
    description: 'Чат-виджет ИИ-агента',
  },
  booking: {
    label: 'Онлайн-запись',
    icon: 'cta',
    description: 'Форма бронирования',
  },
};

export function getDefaultBlockContent(type) {
  switch (type) {
    case 'hero':
      return {
        headline: 'Заголовок вашего сайта',
        subheadline: 'Краткое описание предложения',
        ctaText: 'Связаться',
        ctaLink: '#contacts',
      };
    case 'services':
      return {
        title: 'Наши услуги',
        items: [
          { name: 'Услуга 1', description: 'Описание услуги', icon: 'star' },
          { name: 'Услуга 2', description: 'Описание услуги', icon: 'check' },
        ],
      };
    case 'about':
      return {
        title: 'О нас',
        text: 'Расскажите о вашей компании и ценностях.',
      };
    case 'contacts':
      return {
        title: 'Контакты',
        showForm: true,
        contactInfo: {},
      };
    case 'cta':
      return {
        title: 'Готовы начать?',
        subtitle: 'Свяжитесь с нами сегодня',
        buttonText: 'Написать',
        buttonLink: '#contacts',
      };
    case 'footer':
      return {
        companyName: '{{business_name}}',
        copyrightText: `© ${new Date().getFullYear()} Все права защищены`,
      };
    case 'agent-widget':
      return {
        position: 'bottom-right',
        title: 'Онлайн-консультант',
        greeting: 'Здравствуйте! Чем могу помочь?',
        theme: 'dark',
      };
    case 'booking':
      return {
        title: 'Запись на услугу',
        subtitle: 'Выберите услугу, дату и удобное время',
      };
    default:
      return {};
  }
}

export const ADDABLE_BLOCK_TYPES = Object.keys(BLOCK_TYPE_META);
