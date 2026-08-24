/**
 * Website Create Page
 * AI-first website creation wizard (full-page, like project creation)
 */

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import MainLayout from '../../components/Layout';
import ProtectedRoute from '../../components/ProtectedRoute';
import { useNotification } from '../../context/useNotification';
import { NAVIGATION_ROUTES } from '../../config/constants';
import websiteService from '../../services/websiteService';
import agentService from '../../services/agentService';
import projectService from '../../services/projectService';
import '../styles/website-create-page.css';

const STEPS = {
  BRIEF: 'brief',
  GENERATING: 'generating',
  ERROR: 'error',
};

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

const ChevronRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const WebsiteCreatePageContent = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { showError, showInfo } = useNotification();
  const agentIdParam = searchParams.get('agent_id');
  const agentId = agentIdParam ? Number(agentIdParam) : null;
  const projectIdParam = searchParams.get('project_id');
  const projectId = projectIdParam ? Number(projectIdParam) : null;

  const [currentStep, setCurrentStep] = useState(STEPS.BRIEF);
  const [generationError, setGenerationError] = useState(null);
  const [generationLogs, setGenerationLogs] = useState([]);
  const [websiteId, setWebsiteId] = useState(null);
  const generationStartTime = useRef(null);

  const [formData, setFormData] = useState({
    businessName: '',
    businessDescription: '',
    generationBrief: '',
    primaryColor: '#3B82F6',
    darkMode: false,
  });

  useEffect(() => {
    if (!agentId) {
      return;
    }

    let cancelled = false;
    const loadAgent = async () => {
      try {
        const data = await agentService.getById(agentId);
        if (cancelled) {
          return;
        }
        const name = data?.bot_username || data?.name || '';
        const desc = data?.description || data?.welcome_message || data?.system_prompt || '';
        setFormData((prev) => ({
          ...prev,
          businessName: name || prev.businessName,
          businessDescription: desc.length >= 10 ? desc : prev.businessDescription,
        }));
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load agent for website creation:', error);
        }
      }
    };

    loadAgent();
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  useEffect(() => {
    if (!projectId) {
      return;
    }

    let cancelled = false;
    const loadProject = async () => {
      try {
        const project = await projectService.getProject(projectId);
        if (cancelled) {
          return;
        }
        const description = String(project?.description || '').trim();
        setFormData((prev) => ({
          ...prev,
          businessName: project?.name || prev.businessName,
          businessDescription: description.length >= 10 ? description : prev.businessDescription,
        }));
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load project for website creation:', error);
        }
      }
    };

    loadProject();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const isBriefValid = () => (
    formData.businessName.trim().length >= 2 &&
    formData.businessDescription.trim().length >= 10
  );

  const handleSubmitBrief = async () => {
    if (!isBriefValid()) {
      showError('Пожалуйста, заполните название и описание бизнеса');
      return;
    }

    setCurrentStep(STEPS.GENERATING);
    setGenerationError(null);
    setGenerationLogs([]);
    generationStartTime.current = Date.now();

    try {
      const result = await websiteService.createAndGenerate({
        business_name: formData.businessName.trim(),
        business_description: formData.businessDescription.trim(),
        agent_id: agentId || undefined,
        project_id: projectId || undefined,
        generation_brief: formData.generationBrief.trim() || undefined,
        primary_color: formData.primaryColor,
        dark_mode: formData.darkMode,
      });

      if (result?.website_id) {
        setWebsiteId(result.website_id);
        showInfo('Сайт создан, запущена генерация. Обычно это занимает несколько минут.');
      } else {
        throw new Error('Сервис не вернул ID сайта');
      }
    } catch (error) {
      console.error('Failed to create website:', error);
      setGenerationError(error.message || 'Не удалось создать сайт. Попробуйте снова.');
      setCurrentStep(STEPS.ERROR);
    }
  };

  useEffect(() => {
    if (!websiteId || currentStep !== STEPS.GENERATING) {
      return undefined;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const status = await websiteService.getGenerationStatus(websiteId);
        if (cancelled) {
          return;
        }

        setGenerationLogs(status?.runtime_logs || []);

        if (status?.generation_status === 'completed') {
          navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(websiteId));
          return;
        }

        if (status?.generation_status === 'failed') {
          setGenerationError(status?.error || 'Генерация завершилась ошибкой');
          setCurrentStep(STEPS.ERROR);
          return;
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to poll generation status:', error);
        }
      }
    };

    poll();
    const interval = window.setInterval(poll, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [websiteId, currentStep, navigate]);

  const handleRetryGeneration = () => {
    setGenerationError(null);
    setGenerationLogs([]);
    setCurrentStep(STEPS.BRIEF);
  };

  const renderProgressSteps = () => {
    const steps = [
      { key: STEPS.BRIEF, label: 'Бриф', number: 1 },
      { key: STEPS.GENERATING, label: 'Генерация', number: 2 },
    ];

    return (
      <div className="website-create-progress-steps">
        {steps.map((step, index) => (
          <React.Fragment key={step.key}>
            <div
              className={`progress-step ${
                currentStep === step.key ? 'progress-step--active' : ''
              } ${
                (step.key === STEPS.GENERATING && currentStep === STEPS.GENERATING) ||
                (step.key === STEPS.BRIEF && currentStep !== STEPS.BRIEF)
                  ? 'progress-step--completed'
                  : ''
              }`}
            >
              <div className="progress-step-number">{step.number}</div>
              <span>{step.label}</span>
            </div>
            {index < steps.length - 1 && <div className="progress-step-line" />}
          </React.Fragment>
        ))}
      </div>
    );
  };

  const renderBriefStep = () => (
    <div className="website-create-step">
      <div className="website-create-step-header">
        <h2>Создание сайта</h2>
        <p>Расскажите о вашем бизнесе, и AI сгенерирует готовый сайт</p>
      </div>

      <div className="website-create-form">
        <div className="form-group">
          <label htmlFor="business-name">
            Название бизнеса <span className="required">*</span>
          </label>
          <input
            type="text"
            id="business-name"
            value={formData.businessName}
            onChange={(e) => handleInputChange('businessName', e.target.value)}
            placeholder="Например: Студия дизайна «Лого»"
            maxLength={100}
          />
        </div>

        <div className="form-group">
          <label htmlFor="business-description">
            Описание бизнеса <span className="required">*</span>
            <span className="hint">(минимум 10 символов)</span>
          </label>
          <textarea
            id="business-description"
            value={formData.businessDescription}
            onChange={(e) => handleInputChange('businessDescription', e.target.value)}
            placeholder="Опишите, чем занимается бизнес, какие услуги, кто клиенты, город или регион..."
            rows={4}
            maxLength={500}
          />
          <div className="char-count">
            {formData.businessDescription.length} / 500
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="generation-brief">
            Дополнительный бриф для AI
          </label>
          <textarea
            id="generation-brief"
            value={formData.generationBrief}
            onChange={(e) => handleInputChange('generationBrief', e.target.value)}
            placeholder="Например: строгий B2B стиль, акцент на доверии, кейсах и цифрах. Минимум маркетинговой воды."
            rows={3}
            maxLength={1200}
          />
          <div className="char-count">
            {formData.generationBrief.length} / 1200
          </div>
        </div>

        <div className="form-group">
          <span className="website-create-label">Основной цвет</span>
          <div className="website-create-colors">
            {PRESET_COLORS.map((color) => (
              <button
                key={color.value}
                type="button"
                className={`website-create-color-btn${
                  formData.primaryColor === color.value ? ' website-create-color-btn--selected' : ''
                }`}
                onClick={() => handleInputChange('primaryColor', color.value)}
                aria-label={color.name}
                aria-pressed={formData.primaryColor === color.value}
              >
                <span
                  className="website-create-color-swatch"
                  style={{ backgroundColor: color.value }}
                />
                <span className="website-create-color-name">{color.name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <div className="website-create-toggle-row">
            <div>
              <span className="website-create-toggle-label">Тёмная тема</span>
              <span className="website-create-toggle-hint">Сайт будет в тёмных тонах</span>
            </div>
            <button
              type="button"
              className={`website-create-switch${formData.darkMode ? ' website-create-switch--on' : ''}`}
              onClick={() => handleInputChange('darkMode', !formData.darkMode)}
              role="switch"
              aria-checked={formData.darkMode}
              aria-label="Тёмная тема"
            >
              <span className="website-create-switch-knob" />
            </button>
          </div>
        </div>
      </div>

      <div className="website-create-actions">
        {projectId && (
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => navigate(NAVIGATION_ROUTES.PROJECT_WEBSITE(projectId))}
          >
            Отмена
          </button>
        )}
        <button
          type="button"
          className="btn btn-black"
          onClick={handleSubmitBrief}
          disabled={!isBriefValid()}
        >
          Создать сайт
          <ChevronRightIcon />
        </button>
      </div>
    </div>
  );

  const renderGeneratingStep = () => (
    <div className="website-create-step website-create-step--centered">
      <div className="website-create-loading">
        <div className="website-create-spinner" />
        <h3>Генерируем сайт...</h3>
        <p>AI создаёт уникальный дизайн и контент на основе вашего брифа</p>
        <div className="website-create-progress">
          <div className="website-create-progress-bar" />
        </div>
        {generationLogs.length > 0 && (
          <div className="website-create-logs">
            {generationLogs.slice(-5).map((log, index) => (
              <p key={index} className="website-create-log-line">{log}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const renderErrorStep = () => (
    <div className="website-create-step website-create-step--centered">
      <div className="website-create-error">
        <div className="website-create-error-icon">⚠️</div>
        <h3>Не удалось сгенерировать сайт</h3>
        <p>{generationError}</p>
        <div className="website-create-error-actions">
          <button
            type="button"
            className="btn btn-black"
            onClick={handleRetryGeneration}
          >
            Вернуться к брифу
          </button>
          {websiteId && (
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(websiteId))}
            >
              Открыть в конструкторе
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <MainLayout>
      <div className="website-create-page">
        {renderProgressSteps()}

        <div className="website-create-container">
          {currentStep === STEPS.BRIEF && renderBriefStep()}
          {currentStep === STEPS.GENERATING && renderGeneratingStep()}
          {currentStep === STEPS.ERROR && renderErrorStep()}
        </div>
      </div>
    </MainLayout>
  );
};

const WebsiteCreatePage = () => (
  <ProtectedRoute>
    <WebsiteCreatePageContent />
  </ProtectedRoute>
);

export default WebsiteCreatePage;
