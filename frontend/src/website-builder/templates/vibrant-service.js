/**
 * Vibrant Service Template
 * Яркий стиль с цветными карточками, подходит для услуг
 */

export const VIBRANT_SERVICE_TEMPLATE = {
  id: 'vibrant-service',
  name: 'Яркий сервис',
  description: 'Яркий стиль с цветными карточками, идеально подходит для услуг',
  thumbnail: '/templates/vibrant-service-thumb.jpg',

  // Default styles for this template
  defaultStyles: {
    primaryColor: '#F59E0B',        // Amber
    secondaryColor: '#D97706',      // Darker amber
    accentColor: '#EF4444',         // Red
    backgroundColor: '#FFFBEB',     // Light amber background
    textColor: '#1F2937',
    fontFamily: 'Inter, system-ui, sans-serif',
    darkMode: false,
    borderRadius: '1rem',           // rounded-2xl (playful)
  },

  // Default blocks structure
  defaultBlocks: {
    blocks: [
      {
        type: 'hero',
        order: 1,
        content: {
          headline: 'Яркие решения для вашего бизнеса!',
          subheadline: 'Мы добавим красок в вашу работу и сделаем её незабываемой',
          ctaText: 'Заказать услугу',
          ctaLink: '#contacts',
        },
      },
      {
        type: 'services',
        order: 2,
        content: {
          title: 'Популярные услуги',
          items: [
            { name: 'Экспресс-услуга', description: 'Быстро и качественно', price: 'от 1 000 ₽', icon: 'star' },
            { name: 'Комплексное решение', description: 'Всё включено', price: 'от 5 000 ₽', icon: 'check' },
            { name: 'VIP-обслуживание', description: 'Премиальный сервис', price: 'от 10 000 ₽', icon: 'heart' },
          ],
        },
      },
      {
        type: 'about',
        order: 3,
        content: {
          title: 'Почему выбирают нас?',
          text: 'Мы не просто выполняем работу — мы создаём эмоции! Наш подход сочетает профессионализм с творческим подходом, чтобы каждый клиент получил не просто услугу, а настоящее впечатление.',
        },
      },
      {
        type: 'cta',
        order: 4,
        content: {
          title: 'Есть вопросы?',
          subtitle: 'Наши специалисты всегда рады помочь!',
          buttonText: 'Позвонить сейчас',
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
          companyName: 'Яркий сервис',
          copyrightText: `© ${new Date().getFullYear()} Сделано с любовью ❤️`,
        },
      },
    ],
  },

  // Custom CSS overrides
  cssOverrides: `
    .vibrant-service .services-block .grid > div {
      border: 2px solid #FCD34D;
      transition: all 0.3s ease;
    }
    .vibrant-service .services-block .grid > div:hover {
      transform: rotate(1deg) scale(1.02);
      border-color: #F59E0B;
    }
  `,
};

export default VIBRANT_SERVICE_TEMPLATE;
