/**
 * Main Page
 * Landing page with features overview
 */

import React, { useState } from 'react';
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

const TESTIMONIALS = [
  {
    id: 'review-1',
    name: 'Анастасия, владелец сети салонов',
    company: 'Lumi Beauty',
    text: 'С RSD мы закрыли большую часть типовых вопросов в Telegram. Администраторы перестали отвечать по шаблону в ручном режиме и теперь больше времени уделяют записи клиентов.',
  },
  {
    id: 'review-2',
    name: 'Руслан, операционный директор',
    company: 'GreenBox Logistics',
    text: 'За первую неделю запустили агента для входящих обращений от партнеров. Сократилось количество эскалаций, а ответы по SLA стали заметно стабильнее.',
  },
  {
    id: 'review-3',
    name: 'Марина, основатель онлайн-школы',
    company: 'Focus Learning',
    text: 'Мы загрузили базу материалов и регламенты, и агент начал помогать ученикам 24/7. Команда поддержки обрабатывает сложные кейсы, а не повторяющиеся вопросы.',
  },
  {
    id: 'review-4',
    name: 'Илья, руководитель продаж',
    company: 'TechNova',
    text: 'Агент берет первый контакт и квалификацию заявок. Менеджеры получают уже подготовленные диалоги и быстрее доводят клиентов до демо.',
  },
];

const IMPACT_METRICS = [
  {
    id: 'requests',
    value: 'до 68%',
    label: 'типовых запросов автоматизируется',
  },
  {
    id: 'launch',
    value: '1-2 дня',
    label: 'на запуск пилотного агента',
  },
  {
    id: 'channels',
    value: '3 канала',
    label: 'поддержки чаще всего закрывают одним сценарием',
  },
  {
    id: 'team',
    value: 'x2',
    label: 'быстрее подключаются новые сотрудники',
  },
];

const LAUNCH_STEPS = [
  'Определяете роль агента и собираете 10-15 частых вопросов.',
  'Добавляете базу знаний: документы, правила, тон коммуникации.',
  'Тестируете сценарии на реальных диалогах и уточняете ответы.',
  'Запускаете в рабочем канале и отслеживаете метрики качества.',
];

const Main = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [activeTestimonialIndex, setActiveTestimonialIndex] = useState(0);

  const handleCreateAgent = () => {
    if (isAuthenticated) {
      navigate(NAVIGATION_ROUTES.CREATE_AGENT);
    } else {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  };

  const handlePricing = () => navigate(NAVIGATION_ROUTES.PRICING);
  const handleNextTestimonial = () =>
    setActiveTestimonialIndex((prev) => (prev + 1) % TESTIMONIALS.length);
  const handlePrevTestimonial = () =>
    setActiveTestimonialIndex((prev) => (prev - 1 + TESTIMONIALS.length) % TESTIMONIALS.length);

  const activeTestimonial = TESTIMONIALS[activeTestimonialIndex];

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

        <section className="testimonials" aria-labelledby="testimonials-heading">
          <h2 id="testimonials-heading" className="section-title">
            Как это работает у владельцев бизнеса
          </h2>
          <p className="section-lead section-lead-tight">
            Ниже — примеры команд, которые уже внедрили агентов в поддержку, продажи и обучение клиентов.
          </p>
          <div className="testimonial-carousel" aria-live="polite">
            <article className="testimonial-card">
              <p className="testimonial-text">"{activeTestimonial.text}"</p>
              <p className="testimonial-author">
                {activeTestimonial.name}
                <span>{activeTestimonial.company}</span>
              </p>
            </article>
            <div className="testimonial-controls">
              <button type="button" className="btn btn-outline testimonial-nav-btn" onClick={handlePrevTestimonial}>
                Назад
              </button>
              <div className="testimonial-dots" role="tablist" aria-label="Отзывы">
                {TESTIMONIALS.map((item, index) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`testimonial-dot ${index === activeTestimonialIndex ? 'is-active' : ''}`}
                    onClick={() => setActiveTestimonialIndex(index)}
                    aria-label={`Показать отзыв ${index + 1}`}
                    aria-selected={index === activeTestimonialIndex}
                    role="tab"
                  />
                ))}
              </div>
              <button type="button" className="btn btn-outline testimonial-nav-btn" onClick={handleNextTestimonial}>
                Далее
              </button>
            </div>
          </div>
        </section>

        <section className="impact-section" aria-labelledby="impact-heading">
          <h2 id="impact-heading" className="section-title">
            Что обычно меняется после внедрения
          </h2>
          <div className="impact-grid">
            {IMPACT_METRICS.map((metric) => (
              <article key={metric.id} className="impact-card">
                <p className="impact-value">{metric.value}</p>
                <p className="impact-label">{metric.label}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="launch-roadmap" aria-labelledby="launch-roadmap-heading">
          <h2 id="launch-roadmap-heading" className="section-title">
            Сценарий запуска за 4 шага
          </h2>
          <ol className="roadmap-list">
            {LAUNCH_STEPS.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
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