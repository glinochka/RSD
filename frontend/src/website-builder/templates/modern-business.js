/**
 * Modern Business Template
 * Современный корпоративный стиль с градиентами и крупной типографикой
 */

export const MODERN_BUSINESS_TEMPLATE = {
  id: 'modern-business',
  name: 'Современный бизнес',
  description: 'Современный корпоративный стиль с градиентами и крупной типографикой',
  thumbnail: '/templates/modern-business-thumb.jpg',

  // Default styles for this template
  defaultStyles: {
    primaryColor: '#6366F1',      // Indigo
    secondaryColor: '#4F46E5',      // Darker indigo
    accentColor: '#8B5CF6',         // Purple
    backgroundColor: '#FFFFFF',
    textColor: '#1F2937',
    fontFamily: 'Inter, system-ui, sans-serif',
    darkMode: false,
    borderRadius: '0.75rem',        // rounded-xl
  },

  // Default blocks structure
  defaultBlocks: {
    blocks: [
      {
        type: 'hero',
        order: 1,
        content: {
          headline: 'Ваш успешный бизнес начинается здесь',
          subheadline: 'Профессиональные решения для роста вашей компании',
          ctaText: 'Начать сейчас',
          ctaLink: '#contacts',
        },
      },
      {
        type: 'services',
        order: 2,
        content: {
          title: 'Наши услуги',
          items: [
            { name: 'Консалтинг', description: 'Стратегическое планирование', icon: 'star' },
            { name: 'Разработка', description: 'Современные IT-решения', icon: 'check' },
            { name: 'Поддержка', description: '24/7 клиентский сервис', icon: 'heart' },
          ],
        },
      },
      {
        type: 'about',
        order: 3,
        content: {
          title: 'О нашей компании',
          text: 'Мы — команда профессионалов, преданных делу создания ценности для наших клиентов. С многолетним опытом в отрасли, мы предлагаем комплексные решения, адаптированные под ваши уникальные потребности.',
        },
      },
      {
        type: 'cta',
        order: 4,
        content: {
          title: 'Готовы к сотрудничеству?',
          subtitle: 'Свяжитесь с нами сегодня и получите бесплатную консультацию',
          buttonText: 'Связаться',
          buttonLink: '#contacts',
        },
      },
      {
        type: 'contacts',
        order: 5,
        content: {
          title: 'Контакты',
          showForm: true,
        },
      },
      {
        type: 'footer',
        order: 6,
        content: {
          companyName: 'Моя компания',
          copyrightText: `© ${new Date().getFullYear()} Все права защищены`,
        },
      },
    ],
  },

  // Custom CSS overrides (optional)
  cssOverrides: `
    .modern-business .hero-block h1 {
      background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
  `,
};

export default MODERN_BUSINESS_TEMPLATE;
