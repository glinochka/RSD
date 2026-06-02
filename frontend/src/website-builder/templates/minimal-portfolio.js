/**
 * Minimal Portfolio Template
 * Минималистичный стиль с большим whitespace, чёрно-белый + акцент
 */

export const MINIMAL_PORTFOLIO_TEMPLATE = {
  id: 'minimal-portfolio',
  name: 'Минималистичный',
  description: 'Минималистичный стиль с большим пространством, чёрно-белый + акцентный цвет',
  thumbnail: '/templates/minimal-portfolio-thumb.jpg',

  // Default styles for this template
  defaultStyles: {
    primaryColor: '#000000',        // Black
    secondaryColor: '#333333',      // Dark gray
    accentColor: '#DC2626',         // Red accent
    backgroundColor: '#FAFAFA',     // Off-white
    textColor: '#171717',           // Near-black
    fontFamily: 'system-ui, -apple-system, sans-serif',
    darkMode: false,
    borderRadius: '0.25rem',        // rounded-sm (minimal)
  },

  // Default blocks structure
  defaultBlocks: {
    blocks: [
      {
        type: 'hero',
        order: 1,
        content: {
          headline: 'Простота. Качество. Результат.',
          subheadline: 'Минималистичный подход к максимальному эффекту',
          ctaText: 'Посмотреть работы',
          ctaLink: '#services',
        },
      },
      {
        type: 'about',
        order: 2,
        content: {
          title: 'О нас',
          text: 'Мы верим в силу минимализма. Каждый элемент имеет своё предназначение. Ничего лишнего — только то, что действительно важно для достижения ваших целей.',
          imagePosition: 'left',
        },
      },
      {
        type: 'services',
        order: 3,
        content: {
          title: 'Услуги',
          items: [
            { name: 'Дизайн', description: 'Чистый, функциональный дизайн', icon: 'star' },
            { name: 'Разработка', description: 'Лёгкий, быстрый код', icon: 'check' },
            { name: 'Консалтинг', description: 'Стратегические решения', icon: 'users' },
          ],
        },
      },
      {
        type: 'contacts',
        order: 4,
        content: {
          title: 'Связаться',
          showForm: true,
        },
      },
      {
        type: 'footer',
        order: 5,
        content: {
          companyName: '',
          copyrightText: `© ${new Date().getFullYear()}`,
        },
      },
    ],
  },

  // Custom CSS overrides
  cssOverrides: `
    .minimal-portfolio {
      letter-spacing: -0.025em;
    }
    .minimal-portfolio .hero-block h1 {
      font-weight: 300;
      letter-spacing: -0.04em;
    }
  `,
};

export default MINIMAL_PORTFOLIO_TEMPLATE;
