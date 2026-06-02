/**
 * Elegant Professional Template
 * Элегантный стиль с serif-шрифтами, для консалтинга и юруслуг
 */

export const ELEGANT_PROFESSIONAL_TEMPLATE = {
  id: 'elegant-professional',
  name: 'Элегантный профессионал',
  description: 'Элегантный стиль с классическими шрифтами, идеален для консалтинга и юридических услуг',
  thumbnail: '/templates/elegant-professional-thumb.jpg',

  // Default styles for this template
  defaultStyles: {
    primaryColor: '#1E3A5F',        // Navy blue
    secondaryColor: '#0F172A',      // Dark navy
    accentColor: '#B45309',         // Amber brown
    backgroundColor: '#FDFBF7',     // Cream
    textColor: '#1C1917',           // Stone black
    fontFamily: 'Georgia, "Times New Roman", serif',
    darkMode: false,
    borderRadius: '0.125rem',       // rounded-sm (subtle)
  },

  // Default blocks structure
  defaultBlocks: {
    blocks: [
      {
        type: 'hero',
        order: 1,
        content: {
          headline: 'Экспертность. Надёжность. Результат.',
          subheadline: 'Профессиональные юридические и консалтинговые услуги',
          ctaText: 'Получить консультацию',
          ctaLink: '#contacts',
        },
      },
      {
        type: 'about',
        order: 2,
        content: {
          title: 'Наш опыт — ваше преимущество',
          text: 'Более 15 лет мы предоставляем высококачественные юридические услуги корпоративным клиентам и частным лицам. Наша команда сертифицированных специалистов гарантирует конфиденциальность, профессионализм и достижение поставленных целей.',
          imagePosition: 'right',
        },
      },
      {
        type: 'services',
        order: 3,
        content: {
          title: 'Специализация',
          items: [
            { name: 'Корпоративное право', description: 'Сопровождение бизнеса', icon: 'shield' },
            { name: 'Контрактное право', description: 'Договорная работа', icon: 'check' },
            { name: 'Консультации', description: 'Правовые экспертизы', icon: 'users' },
          ],
        },
      },
      {
        type: 'cta',
        order: 4,
        content: {
          title: 'Нужна профессиональная помощь?',
          subtitle: 'Доверьте ваши вопросы экспертам',
          buttonText: 'Записаться на консультацию',
          buttonLink: '#contacts',
        },
      },
      {
        type: 'contacts',
        order: 5,
        content: {
          title: 'Свяжитесь с нами',
          showForm: true,
        },
      },
      {
        type: 'footer',
        order: 6,
        content: {
          companyName: 'Юридическая компания',
          copyrightText: `© ${new Date().getFullYear()} Все права защищены. Лицензия № 12345.`,
        },
      },
    ],
  },

  // Custom CSS overrides
  cssOverrides: `
    .elegant-professional {
      font-family: Georgia, "Times New Roman", serif;
    }
    .elegant-professional h1, 
    .elegant-professional h2, 
    .elegant-professional h3 {
      font-weight: 400;
      letter-spacing: 0.02em;
    }
    .elegant-professional .hero-block h1 {
      font-size: 3rem;
      line-height: 1.2;
    }
    .elegant-professional button,
    .elegant-professional .cta-block a {
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 0.875rem;
    }
    .elegant-professional .services-block .grid > div {
      border: 1px solid #E7E5E4;
    }
  `,
};

export default ELEGANT_PROFESSIONAL_TEMPLATE;
