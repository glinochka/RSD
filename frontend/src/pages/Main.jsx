/**
 * Main Page
 * Landing page with features overview
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import MainLayout from '../components/Layout';
import AgentChatShowcase from '../components/AgentChatShowcase';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/main.css';

const VALUE_HIGHLIGHTS = [
  {
    id: 'time',
    title: 'Меньше рутины',
    text: 'Типовые вопросы закрывает агент — ваша команда подключается там, где нужен человек.',
  },
  {
    id: 'context',
    title: 'Ваш контекст',
    text: 'Регламенты, прайсы и инструкции остаются основой ответов: агент опирается на то, что вы ему доверили.',
  },
  {
    id: 'start',
    title: 'Быстрый старт',
    text: 'Роль, промпт, документы — и диалог в Telegram можно запускать без ожидания разработки.',
  },
];

const FEATURES = [
  {
    id: 'simplicity',
    title: 'Простота',
    items: [
      'Выберите роль агента',
      'Напишите промпт',
      'Загрузите файлы',
      'Получите ИИ-агента',
    ],
  },
  {
    id: 'security',
    title: 'Безопасность',
    description:
      'Шифрование и аккуратная работа с данными — чтобы спокойно использовать платформу для рабочей информации.',
  },
  {
    id: 'bigdata',
    title: 'Умный отбор',
    description:
      'Алгоритмы помогают находить релевантные фрагменты в больших объёмах текста — без лишнего «шума» в ответах.',
  },
];

const FOR_WHOM = [
  {
    id: 'smb',
    title: 'Малый и средний бизнес',
    text: 'Сервисы, студии и онлайн-торговля — когда важен понятный первый контакт и стабильные ответы по вашим правилам.',
  },
  {
    id: 'teams',
    title: 'Поддержка и продажи',
    text: 'Единый источник правды по продукту и политикам: меньше повторов и быстрее согласованные формулировки.',
  },
  {
    id: 'experts',
    title: 'Эксперты и консультанты',
    text: 'Масштабируйте типовые разъяснения и онбординг, не размывая личный стиль общения.',
  },
];

const Main = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const handleCreateAgent = () => {
    if (isAuthenticated) {
      navigate(NAVIGATION_ROUTES.CREATE_AGENT);
    } else {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  };

  const handlePricing = () => navigate(NAVIGATION_ROUTES.PRICING);

  return (
    <MainLayout>
      <div className="main-content">
        <section className="hero" aria-labelledby="hero-heading">
          <div className="hero-content">
            <h1 id="hero-heading">Ваш бизнес.</h1>
            <div className="highlight">Ваши знания.</div>
            <h2>Ваш сотрудник.</h2>
            <p className="description">
              RSD — no-code платформа для ИИ-агентов под поддержку, продажи и внутренние процессы. Соберите сценарий без
              разработчиков: ответы опираются на ваши документы и тон общения, который вы задаёте сами.
            </p>
            <p className="description-lead">
              Меньше ожидания в чатах и проще онбординг — при этом вы по-прежнему контролируете, что именно говорит агент.
            </p>
            <div className="hero-actions">
              <button type="button" className="btn btn-black" onClick={handleCreateAgent}>
                Создать агента
              </button>
              <button type="button" className="btn btn-outline hero-actions-secondary" onClick={handlePricing}>
                Тарифы
              </button>
            </div>
          </div>
          <div className="hero-media">
            <AgentChatShowcase tone="light" variant="main" />
          </div>
        </section>

        <section className="value-highlights" aria-labelledby="value-highlights-heading">
          <h2 id="value-highlights-heading" className="section-title">
            Что даёт платформа на практике
          </h2>
          <p className="section-lead">
            Не обещаем «магии» — даём понятный инструмент: вы настраиваете роль, знания и канал общения.
          </p>
          <div className="value-highlights-grid">
            {VALUE_HIGHLIGHTS.map((block) => (
              <article key={block.id} className="value-highlight-card">
                <h3>{block.title}</h3>
                <p>{block.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="features" aria-labelledby="features-heading">
          <h2 id="features-heading" className="section-title">
            Как устроена платформа
          </h2>
          <p className="section-lead section-lead-tight">
            Один поток от идеи до работающего агента — с упором на безопасность и релевантность ответов.
          </p>
          <div className="features-grid">
            {FEATURES.map((feature) => (
              <div key={feature.id} className="feature-card">
                <h4>{feature.title}</h4>
                {feature.items ? (
                  <ul>
                    {feature.items.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>{feature.description}</p>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="audience-section" aria-labelledby="audience-heading">
          <h2 id="audience-heading" className="section-title">
            Кому подойдёт RSD
          </h2>
          <div className="audience-grid">
            {FOR_WHOM.map((item) => (
              <article key={item.id} className="audience-card">
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="cta-band" aria-labelledby="cta-heading">
          <div className="cta-band-inner">
            <h2 id="cta-heading">Начните с одного агента</h2>
            <p>
              Соберите прототип за несколько минут: роль и базу знаний всегда можно уточнить позже. Если удобнее сначала
              сравнить условия — загляните в раздел с тарифами.
            </p>
            <div className="cta-band-actions">
              <button type="button" className="btn btn-black" onClick={handleCreateAgent}>
                Создать агента
              </button>
              <button type="button" className="btn btn-outline" onClick={handlePricing}>
                Посмотреть тарифы
              </button>
            </div>
          </div>
        </section>
      </div>
    </MainLayout>
  );
};

export default Main;