/**
 * Project Create Page
 * AI-first project creation wizard (Stage 7 - Connected to real API)
 */

import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../../components/Layout';
import CustomSelect from '../../components/CustomSelect';
import { useAuth } from '../../context/useAuth';
import { useNotification } from '../../context/useNotification';
import { NAVIGATION_ROUTES } from '../../config/constants';
import projectService from '../../services/projectService';
import { projectPlanMock } from '../../mocks/projectPlanMock';
import '../../styles/projectCreatePage.css';

// Industry options
const INDUSTRY_OPTIONS = [
  { value: 'retail', label: 'Ритейл' },
  { value: 'beauty_salon', label: 'Салон красоты' },
  { value: 'restaurant', label: 'Ресторан / Кафе' },
  { value: 'medical', label: 'Медицина / Клиника' },
  { value: 'education', label: 'Образование / Курсы' },
  { value: 'b2b_services', label: 'B2B услуги' },
  { value: 'logistics', label: 'Логистика / Доставка' },
  { value: 'real_estate', label: 'Недвижимость' },
  { value: 'finance', label: 'Финансы / Страхование' },
  { value: 'other', label: 'Другое' },
];

// Steps
const STEPS = {
  BRIEF: 'brief',
  GENERATING: 'generating',
  PREVIEW: 'preview',
  APPLYING: 'applying',
};

// Icons
const ChevronLeftIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const BotIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
  </svg>
);

const GlobeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const ProjectCreatePage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError, showInfo } = useNotification();

  const [currentStep, setCurrentStep] = useState(STEPS.BRIEF);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [generatedPlan, setGeneratedPlan] = useState(null);
  const [selectedAgents, setSelectedAgents] = useState([]);
  const [includeWebsite, setIncludeWebsite] = useState(true);
  
  // Stage 7: Timing and error handling
  const [generationTime, setGenerationTime] = useState(null);
  const [generationError, setGenerationError] = useState(null);
  const generationStartTime = useRef(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    industry: '',
    industry_custom: '',
    description: '',
  });

  // Redirect if not authenticated
  if (!isAuthenticated) {
    navigate(NAVIGATION_ROUTES.AUTH);
    return null;
  }

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const getBriefPayload = () => ({
    name: formData.name.trim(),
    industry: formData.industry === 'other'
      ? formData.industry_custom.trim()
      : formData.industry,
    description: formData.description.trim(),
  });

  const isBriefValid = () => {
    const industryValid = formData.industry
      && (formData.industry !== 'other' || formData.industry_custom.trim().length >= 2);

    return (
      formData.name.trim().length >= 2 &&
      industryValid &&
      formData.description.trim().length >= 50
    );
  };

  const handleSubmitBrief = async () => {
    if (!isBriefValid()) {
      showError('Пожалуйста, заполните все обязательные поля');
      return;
    }

    setCurrentStep(STEPS.GENERATING);
    setIsGenerating(true);
    setGenerationError(null);
    generationStartTime.current = Date.now();

    try {
      // Call real API
      const plan = await projectService.generatePlan(getBriefPayload());
      
      // Calculate generation time
      const elapsed = ((Date.now() - generationStartTime.current) / 1000).toFixed(1);
      setGenerationTime(elapsed);
      
      setGeneratedPlan(plan);
      setSelectedAgents(plan.agents.map((_, index) => index));
      setIncludeWebsite(plan.website?.enabled || false);
      setCurrentStep(STEPS.PREVIEW);
    } catch (error) {
      console.error('Failed to generate plan:', error);
      setGenerationError(error.message || 'Не удалось сгенерировать план');
      
      // In development, fallback to mock on error
      if (process.env.NODE_ENV === 'development') {
        showInfo('Используем демо-данные (API недоступен)');
        setTimeout(() => {
          setGeneratedPlan(projectPlanMock);
          setSelectedAgents(projectPlanMock.agents.map((_, index) => index));
          setIncludeWebsite(projectPlanMock.website.enabled);
          setGenerationTime('2.0');
          setCurrentStep(STEPS.PREVIEW);
        }, 1000);
      } else {
        setIsGenerating(false);
        showError(error.message || 'Не удалось сгенерировать план. Попробуйте снова.');
      }
    } finally {
      if (process.env.NODE_ENV !== 'development' || !generationError) {
        setIsGenerating(false);
      }
    }
  };

  const handleRetryGeneration = () => {
    setGenerationError(null);
    handleSubmitBrief();
  };

  const handleToggleAgent = (index) => {
    setSelectedAgents((prev) => {
      if (prev.includes(index)) {
        return prev.filter((i) => i !== index);
      }
      return [...prev, index];
    });
  };

  const handleApplyPlan = async () => {
    if (!generatedPlan) return;

    setCurrentStep(STEPS.APPLYING);
    setIsApplying(true);

    try {
      // Generate idempotency key
      const idempotencyKey = `project-create-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      // Filter selected agents
      const filteredPlan = {
        ...generatedPlan,
        agents: generatedPlan.agents.filter((_, index) => selectedAgents.includes(index)),
        website: {
          ...generatedPlan.website,
          enabled: includeWebsite && generatedPlan.website?.enabled,
        },
      };

      // Call API to apply plan
      const result = await projectService.applyPlan(getBriefPayload(), filteredPlan, idempotencyKey);

      // Show onboarding toast
      if (result.status === 'partial') {
        showInfo('Проект создан! Сайт будет доступен позже. Подключите мессенджер в разделе Агенты');
      } else {
        showInfo('Проект создан! Подключите мессенджер в разделе Агенты');
      }

      // Navigate to project dashboard
      navigate(NAVIGATION_ROUTES.PROJECT_DETAIL(result.project_id));
    } catch (error) {
      console.error('Failed to apply plan:', error);
      setIsApplying(false);
      showError(error.message || 'Не удалось создать проект. Попробуйте снова.');

      // Show retry option
      if (window.confirm('Не удалось создать проект. Попробовать снова?')) {
        handleApplyPlan();
      } else {
        setCurrentStep(STEPS.PREVIEW);
      }
    }
  };

  const handleBack = () => {
    if (currentStep === STEPS.PREVIEW) {
      setCurrentStep(STEPS.BRIEF);
    }
  };

  // Render Brief Step
  const renderBriefStep = () => (
    <div className="project-create-step">
      <div className="project-create-step-header">
        <h2>Создание проекта</h2>
        <p>Расскажите о вашем бизнесе, и AI подготовит план цифровизации</p>
      </div>

      <div className="project-create-form">
        <div className="form-group">
          <label htmlFor="name">
            Название бизнеса / отдела <span className="required">*</span>
          </label>
          <input
            type="text"
            id="name"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            placeholder="Например: Салон красоты Люмьер"
            maxLength={200}
          />
        </div>

        <div className="form-group">
          <label htmlFor="industry">
            Отрасль <span className="required">*</span>
          </label>
          <CustomSelect
            id="industry"
            name="industry"
            value={formData.industry}
            placeholder="Выберите отрасль"
            options={INDUSTRY_OPTIONS}
            onChange={(e) => {
              const value = e.target.value;
              setFormData((prev) => ({
                ...prev,
                industry: value,
                industry_custom: value === 'other' ? prev.industry_custom : '',
              }));
            }}
          />
        </div>

        {formData.industry === 'other' && (
          <div className="form-group">
            <label htmlFor="industry_custom">
              Укажите отрасль <span className="required">*</span>
            </label>
            <input
              type="text"
              id="industry_custom"
              value={formData.industry_custom}
              onChange={(e) => handleInputChange('industry_custom', e.target.value)}
              placeholder="Например: Автосервис"
              maxLength={64}
            />
          </div>
        )}

        <div className="form-group">
          <label htmlFor="description">
            Краткое описание <span className="required">*</span>
            <span className="hint">(минимум 50 символов)</span>
          </label>
          <textarea
            id="description"
            value={formData.description}
            onChange={(e) => handleInputChange('description', e.target.value)}
            placeholder="Опишите, чем занимается бизнес, какие услуги, кто клиенты, город или регион (например: Москва)..."
            rows={4}
            maxLength={800}
          />
          <div className="char-count">
            {formData.description.length} / 800
          </div>
        </div>
      </div>

      <div className="project-create-actions">
        <button
          type="button"
          className="btn btn-black"
          onClick={handleSubmitBrief}
          disabled={!isBriefValid()}
        >
          Далее
          <ChevronRightIcon />
        </button>
      </div>
    </div>
  );

  // Render Generating Step
  const renderGeneratingStep = () => (
    <div className="project-create-step project-create-step--centered">
      {generationError ? (
        <div className="project-create-error">
          <div className="project-create-error-icon">⚠️</div>
          <h3>Не удалось сгенерировать план</h3>
          <p>{generationError}</p>
          <div className="project-create-error-actions">
            <button
              type="button"
              className="btn btn-black"
              onClick={handleRetryGeneration}
            >
              Попробовать снова
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                setGenerationError(null);
                setCurrentStep(STEPS.BRIEF);
              }}
            >
              Вернуться к брифу
            </button>
          </div>
        </div>
      ) : (
        <div className="project-create-loading">
          <div className="project-create-spinner" />
          <h3>Генерируем решение...</h3>
          <p>AI анализирует ваш бизнес и подбирает оптимальную конфигурацию</p>
          <div className="project-create-progress">
            <div className="project-create-progress-bar" />
          </div>
        </div>
      )}
    </div>
  );

  // Render Preview Step
  const renderPreviewStep = () => {
    if (!generatedPlan) return null;

    return (
      <div className="project-create-step">
        <div className="project-create-step-header">
          <h2>Предпросмотр плана</h2>
          <p>
            Проверьте предложенную конфигурацию и выберите, что включить
            {generationTime && (
              <span className="generation-time"> (собрано за {generationTime} сек)</span>
            )}
          </p>
        </div>

        <div className="project-preview-content">
          {/* Project info */}
          <div className="project-preview-card">
            <h3>Информация о проекте</h3>
            <div className="project-preview-field">
              <label>Название:</label>
              <span>{generatedPlan.project?.name || formData.name}</span>
            </div>
            <div className="project-preview-field">
              <label>Отрасль:</label>
              <span>{generatedPlan.project?.industry || getBriefPayload().industry}</span>
            </div>
          </div>

          {/* Agents */}
          <div className="project-preview-section">
            <h3>Агенты ({generatedPlan.agents?.length || 0})</h3>
            <div className="project-preview-agents">
              {generatedPlan.agents?.map((agent, index) => (
                <div
                  key={index}
                  className={`project-preview-agent-card ${selectedAgents.includes(index) ? '' : 'project-preview-agent-card--disabled'}`}
                >
                  <label className="project-preview-agent-checkbox">
                    <span className="custom-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedAgents.includes(index)}
                        onChange={() => handleToggleAgent(index)}
                      />
                      <span className="custom-checkbox-mark" />
                    </span>
                    <BotIcon />
                  </label>
                  <div className="project-preview-agent-info">
                    <h4>{agent.suggested_name}</h4>
                    <span className="project-preview-agent-type">{agent.template_type}</span>
                    <p className="project-preview-agent-prompt">
                      {agent.system_prompt?.substring(0, 100)}...
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Website */}
          {generatedPlan.website?.enabled && (
            <div className="project-preview-section">
              <h3>Сайт</h3>
              <div className={`project-preview-website-card ${includeWebsite ? '' : 'project-preview-website-card--disabled'}`}>
                <label className="project-preview-website-checkbox">
                  <span className="custom-checkbox">
                    <input
                      type="checkbox"
                      checked={includeWebsite}
                      onChange={() => setIncludeWebsite(!includeWebsite)}
                    />
                    <span className="custom-checkbox-mark" />
                  </span>
                  <GlobeIcon />
                </label>
                <div className="project-preview-website-info">
                  <h4>{generatedPlan.website?.title}</h4>
                  <span className="project-preview-website-slug">
                    /w/{generatedPlan.website?.suggested_slug}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Knowledge recommendations */}
          <div className="project-preview-section">
            <h3>Рекомендуемые документы</h3>
            <ul className="project-preview-knowledge">
              {generatedPlan.knowledge_recommendations?.map((rec, index) => (
                <li key={index}>
                  <CheckIcon />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="project-create-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleBack}
          >
            <ChevronLeftIcon />
            Назад
          </button>
          <button
            type="button"
            className="btn btn-black"
            onClick={handleApplyPlan}
            disabled={selectedAgents.length === 0 && !includeWebsite}
          >
            Запустить проект
          </button>
        </div>
      </div>
    );
  };

  // Render Applying Step
  const renderApplyingStep = () => (
    <div className="project-create-step project-create-step--centered">
      <div className="project-create-loading">
        <div className="project-create-spinner" />
        <h3>Создаем проект...</h3>
        <p>Настраиваем агентов и сайт</p>
        <div className="project-create-progress">
          <div className="project-create-progress-bar" />
        </div>
      </div>
    </div>
  );

  return (
    <MainLayout>
      <div className="project-create-page">
        {/* Progress indicator */}
        <div className="project-create-progress-steps">
          <div className={`progress-step ${currentStep !== STEPS.BRIEF ? 'progress-step--completed' : ''} ${currentStep === STEPS.BRIEF ? 'progress-step--active' : ''}`}>
            <div className="progress-step-number">1</div>
            <span>Бриф</span>
          </div>
          <div className="progress-step-line" />
          <div className={`progress-step ${currentStep === STEPS.PREVIEW || currentStep === STEPS.APPLYING ? 'progress-step--completed' : ''} ${currentStep === STEPS.GENERATING ? 'progress-step--active' : ''}`}>
            <div className="progress-step-number">2</div>
            <span>Генерация</span>
          </div>
          <div className="progress-step-line" />
          <div className={`progress-step ${currentStep === STEPS.APPLYING ? 'progress-step--completed' : ''} ${currentStep === STEPS.PREVIEW ? 'progress-step--active' : ''}`}>
            <div className="progress-step-number">3</div>
            <span>Предпросмотр</span>
          </div>
          <div className="progress-step-line" />
          <div className={`progress-step ${currentStep === STEPS.APPLYING ? 'progress-step--active' : ''}`}>
            <div className="progress-step-number">4</div>
            <span>Запуск</span>
          </div>
        </div>

        {/* Step content */}
        <div className="project-create-container">
          {currentStep === STEPS.BRIEF && renderBriefStep()}
          {currentStep === STEPS.GENERATING && renderGeneratingStep()}
          {currentStep === STEPS.PREVIEW && renderPreviewStep()}
          {currentStep === STEPS.APPLYING && renderApplyingStep()}
        </div>
      </div>
    </MainLayout>
  );
};

export default ProjectCreatePage;
