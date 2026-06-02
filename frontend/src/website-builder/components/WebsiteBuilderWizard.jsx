/**
 * Website Builder Wizard Modal
 * Step-by-step modal for configuring website before AI generation
 */
import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { websiteService } from '../../services/websiteService';
import '../styles/website-builder-wizard.css';

const WEBSITE_TEMPLATES = [
  { id: 'modern-business', name: 'Современный бизнес', description: 'Градиенты, крупная типографика', color: '#3B82F6' },
  { id: 'minimal-portfolio', name: 'Минималистичный', description: 'Много whitespace, чёрно-белый', color: '#1F2937' },
  { id: 'vibrant-service', name: 'Яркий сервис', description: 'Цветные карточки, подходит для услуг', color: '#8B5CF6' },
  { id: 'elegant-professional', name: 'Элегантный', description: 'Serif-шрифты, для консалтинга', color: '#059669' },
];

const PRESET_COLORS = [
  { name: 'Синий', value: '#3B82F6' },
  { name: 'Фиолетовый', value: '#8B5CF6' },
  { name: 'Зелёный', value: '#10B981' },
  { name: 'Оранжевый', value: '#F59E0B' },
  { name: 'Красный', value: '#EF4444' },
  { name: 'Розовый', value: '#EC4899' },
  { name: 'Бирюзовый', value: '#06B6D4' },
  { name: 'Серый', value: '#6B7280' },
];

const CloseIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const InfoIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const LayoutIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
  </svg>
);

const PaletteIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
  </svg>
);

const CheckIcon = () => (
  <svg className="wb-wizard__template-check" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
  </svg>
);

const WebsiteBuilderWizard = ({ isOpen, onClose, agent, onSuccess }) => {
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [businessName, setBusinessName] = useState('');
  const [businessDescription, setBusinessDescription] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('modern-business');
  const [primaryColor, setPrimaryColor] = useState('#3B82F6');
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    if (agent && isOpen) {
      const name = agent.bot_username || agent.name || 'Мой сайт';
      const desc = agent.description || agent.welcome_message || agent.system_prompt || '';
      setBusinessName(name);
      setBusinessDescription(
        desc.length >= 10 ? desc : `${desc}. Сайт с описанием услуг и выгод для клиентов.`
      );
    }
  }, [agent, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setStep(1);
      setError(null);
      setIsSubmitting(false);
      return undefined;
    }

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (e) => {
      if (e.key === 'Escape' && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, isSubmitting, onClose]);

  if (!isOpen) return null;

  const totalSteps = 3;

  const handleOverlayClick = () => {
    if (!isSubmitting) onClose();
  };

  const handleNext = () => {
    if (step < totalSteps) setStep(step + 1);
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleSubmit = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const result = await websiteService.createAndGenerate({
        business_name: businessName.trim() || 'Мой сайт',
        business_description:
          businessDescription.trim() || 'Сайт с описанием услуг и выгод для клиентов.',
        agent_id: agent?.id,
        template_id: selectedTemplate,
        primary_color: primaryColor,
        dark_mode: darkMode,
      });

      if (result?.website_id) {
        onSuccess(result.website_id);
        onClose();
      } else {
        throw new Error('Сервис не вернул ID сайта');
      }
    } catch (err) {
      setError(err?.message || 'Не удалось создать сайт. Попробуйте снова.');
      setIsSubmitting(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return (
          businessName.trim().length >= 2 && businessDescription.trim().length >= 10
        );
      case 2:
      case 3:
        return true;
      default:
        return false;
    }
  };

  const selectedTemplateName =
    WEBSITE_TEMPLATES.find((t) => t.id === selectedTemplate)?.name || '';

  const modal = (
    <div
      className="wb-wizard-backdrop"
      onClick={handleOverlayClick}
      role="presentation"
    >
      <div
        className="wb-wizard"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="wb-wizard-title"
      >
        <header className="wb-wizard__header">
          <div>
            <h2 id="wb-wizard-title" className="wb-wizard__title">
              Создание сайта за 5 минут
            </h2>
            <p className="wb-wizard__step-label">
              Шаг {step} из {totalSteps}
            </p>
          </div>
          <button
            type="button"
            className="wb-wizard__close"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Закрыть"
          >
            <CloseIcon />
          </button>
        </header>

        <div className="wb-wizard__progress" aria-hidden="true">
          <div
            className="wb-wizard__progress-bar"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>

        <div className="wb-wizard__body">
          {error && (
            <div className="wb-wizard__error" role="alert">
              <InfoIcon />
              <span>{error}</span>
            </div>
          )}

          {step === 1 && (
            <>
              <div className="wb-wizard__intro">
                <div className="wb-wizard__icon-wrap wb-wizard__icon-wrap--accent">
                  <InfoIcon />
                </div>
                <h3 className="wb-wizard__subtitle">Расскажите о вашем бизнесе</h3>
                <p className="wb-wizard__hint">ИИ создаст сайт на основе этой информации</p>
              </div>

              <div className="wb-wizard__field">
                <label className="wb-wizard__label" htmlFor="wb-business-name">
                  Название бизнеса <span className="wb-wizard__required">*</span>
                </label>
                <input
                  id="wb-business-name"
                  type="text"
                  className="wb-wizard__input"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="Например: Студия дизайна «Лого»"
                  maxLength={100}
                  autoFocus
                />
                <p className="wb-wizard__counter">{businessName.length}/100 символов</p>
              </div>

              <div className="wb-wizard__field">
                <label className="wb-wizard__label" htmlFor="wb-business-desc">
                  Описание бизнеса <span className="wb-wizard__required">*</span>
                </label>
                <textarea
                  id="wb-business-desc"
                  className="wb-wizard__textarea"
                  value={businessDescription}
                  onChange={(e) => setBusinessDescription(e.target.value)}
                  placeholder="Опишите, чем занимается ваш бизнес, какие услуги предоставляете..."
                  rows={5}
                  maxLength={500}
                />
                <p className="wb-wizard__counter">
                  Минимум 10 символов • {businessDescription.length}/500
                </p>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <div className="wb-wizard__intro">
                <div className="wb-wizard__icon-wrap wb-wizard__icon-wrap--accent">
                  <LayoutIcon />
                </div>
                <h3 className="wb-wizard__subtitle">Выберите стиль сайта</h3>
                <p className="wb-wizard__hint">Шаблон определяет базовую структуру и дизайн</p>
              </div>

              <div className="wb-wizard__templates">
                {WEBSITE_TEMPLATES.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    className={`wb-wizard__template-card${
                      selectedTemplate === template.id ? ' wb-wizard__template-card--selected' : ''
                    }`}
                    onClick={() => setSelectedTemplate(template.id)}
                  >
                    <div className="wb-wizard__template-inner">
                      <span
                        className="wb-wizard__template-swatch"
                        style={{ backgroundColor: template.color }}
                      />
                      <div>
                        <p className="wb-wizard__template-name">{template.name}</p>
                        <p className="wb-wizard__template-desc">{template.description}</p>
                      </div>
                      {selectedTemplate === template.id && <CheckIcon />}
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="wb-wizard__intro">
                <div className="wb-wizard__icon-wrap wb-wizard__icon-wrap--accent">
                  <PaletteIcon />
                </div>
                <h3 className="wb-wizard__subtitle">Настройте цвета</h3>
                <p className="wb-wizard__hint">Выберите основной цвет бренда</p>
              </div>

              <div className="wb-wizard__field">
                <span className="wb-wizard__label">Основной цвет</span>
                <div className="wb-wizard__colors">
                  {PRESET_COLORS.map((color) => (
                    <button
                      key={color.value}
                      type="button"
                      className={`wb-wizard__color-btn${
                        primaryColor === color.value ? ' wb-wizard__color-btn--selected' : ''
                      }`}
                      onClick={() => setPrimaryColor(color.value)}
                      aria-label={color.name}
                      aria-pressed={primaryColor === color.value}
                    >
                      <span
                        className="wb-wizard__color-swatch"
                        style={{ backgroundColor: color.value }}
                      />
                      <span className="wb-wizard__color-name">{color.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="wb-wizard__field">
                <div className="wb-wizard__toggle-row">
                  <div>
                    <span className="wb-wizard__toggle-label">Тёмная тема</span>
                    <span className="wb-wizard__toggle-hint">Сайт будет в тёмных тонах</span>
                  </div>
                  <button
                    type="button"
                    className={`wb-wizard__switch${darkMode ? ' wb-wizard__switch--on' : ''}`}
                    onClick={() => setDarkMode(!darkMode)}
                    role="switch"
                    aria-checked={darkMode}
                    aria-label="Тёмная тема"
                  >
                    <span className="wb-wizard__switch-knob" />
                  </button>
                </div>
              </div>

              <div className="wb-wizard__summary">
                <p className="wb-wizard__summary-title">Итого</p>
                <ul className="wb-wizard__summary-list">
                  <li>
                    Название: <strong>{businessName}</strong>
                  </li>
                  <li>
                    Шаблон: <strong>{selectedTemplateName}</strong>
                  </li>
                  <li>
                    Цвет:{' '}
                    <span
                      className="wb-wizard__summary-dot"
                      style={{ backgroundColor: primaryColor }}
                    />
                  </li>
                  <li>
                    Тема: <strong>{darkMode ? 'Тёмная' : 'Светлая'}</strong>
                  </li>
                </ul>
              </div>
            </>
          )}
        </div>

        <footer className="wb-wizard__footer">
          <button
            type="button"
            className="btn btn-outline"
            onClick={step === 1 ? onClose : handleBack}
            disabled={isSubmitting}
          >
            {step === 1 ? 'Отмена' : 'Назад'}
          </button>

          <div className="wb-wizard__footer-actions">
            {step < totalSteps ? (
              <button
                type="button"
                className="btn btn-black"
                onClick={handleNext}
                disabled={!canProceed()}
              >
                Далее
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-black"
                onClick={handleSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <span className="wb-wizard__spinner" aria-hidden="true" />
                    Создаём...
                  </>
                ) : (
                  'Создать сайт'
                )}
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};

export default WebsiteBuilderWizard;
