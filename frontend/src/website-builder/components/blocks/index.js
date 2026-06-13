/**
 * Website Builder Block Components
 * Export all block types for the website builder
 */

export { default as HeroBlock } from './HeroBlock';
export { default as ServicesBlock } from './ServicesBlock';
export { default as AboutBlock } from './AboutBlock';
export { default as ContactsBlock } from './ContactsBlock';
export { default as CTABlock } from './CTABlock';
export { default as FooterBlock } from './FooterBlock';
export { default as AgentWidgetBlock } from './AgentWidgetBlock';
export { default as BookingBlock } from './BookingBlock';

// Block registry for dynamic rendering
export const BLOCK_COMPONENTS = {
  hero: 'HeroBlock',
  services: 'ServicesBlock',
  about: 'AboutBlock',
  contacts: 'ContactsBlock',
  cta: 'CTABlock',
  footer: 'FooterBlock',
  'agent-widget': 'AgentWidgetBlock',
  booking: 'BookingBlock',
  custom: 'HeroBlock', // Custom blocks default to hero styling
};

// Block type metadata for UI
export const BLOCK_METADATA = {
  hero: {
    label: 'Hero / Главный экран',
    description: 'Большой заголовок с призывом к действию',
    icon: 'Layout',
  },
  services: {
    label: 'Услуги',
    description: 'Сетка карточек услуг',
    icon: 'Grid',
  },
  about: {
    label: 'О нас',
    description: 'Описание компании с изображением',
    icon: 'Info',
  },
  contacts: {
    label: 'Контакты',
    description: 'Контактная информация и форма',
    icon: 'Mail',
  },
  cta: {
    label: 'Призыв к действию',
    description: 'Блок с кнопкой-действием',
    icon: 'MousePointer',
  },
  footer: {
    label: 'Подвал',
    description: 'Копирайт, ссылки, соцсети',
    icon: 'Anchor',
  },
  'agent-widget': {
    label: 'Виджет агента',
    description: 'Чат-виджет ИИ-агента',
    icon: 'MessageSquare',
  },
  booking: {
    label: 'Онлайн-запись',
    description: 'Форма бронирования услуг',
    icon: 'Calendar',
  },
  custom: {
    label: 'Произвольный блок',
    description: 'Кастомный контент',
    icon: 'Box',
  },
};
