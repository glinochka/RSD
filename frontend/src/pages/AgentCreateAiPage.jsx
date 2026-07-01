import React, { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import MainLayout from '../components/Layout';
import CustomSelect from '../components/CustomSelect';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import agentService from '../services/agentService';
import '../styles/agentCreateAiPage.css';

const TEMPLATE_OPTIONS = [
  { value: 'qa', label: 'Поддержка / FAQ' },
  { value: 'crm_admin', label: 'CRM администратор' },
  { value: 'sales_manager', label: 'Продажи (ИИ МОП)' },
];

const AgentCreateAiPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const { showError, showSuccess } = useNotification();
  const projectIdFromQuery = searchParams.get('projectId');

  const [brief, setBrief] = useState('');
  const [projectContext, setProjectContext] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [draft, setDraft] = useState(null);

  const briefValid = useMemo(() => brief.trim().length >= 20, [brief]);

  if (!isAuthenticated) {
    navigate(NAVIGATION_ROUTES.AUTH);
    return null;
  }

  const handleGenerate = async () => {
    if (!briefValid) {
      showError('Опишите задачу агента минимум 20 символами');
      return;
    }
    setIsGenerating(true);
    try {
      const result = await agentService.aiGenerateDraft({
        brief: brief.trim(),
        project_context: projectContext.trim() || undefined,
      });
      setDraft(result);
    } catch (error) {
      showError(error.message || 'Не удалось сгенерировать заготовку');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDraftChange = (field, value) => {
    setDraft((prev) => ({ ...(prev || {}), [field]: value }));
  };

  const handleCreate = async () => {
    if (!draft) return;
    setIsCreating(true);
    try {
      await agentService.createEmpty({
        system_prompt: (draft.system_prompt || '').trim(),
        template_type: draft.template_type || 'qa',
        template_config: draft.template_config || undefined,
        project_id: projectIdFromQuery ? parseInt(projectIdFromQuery, 10) : undefined,
      });
      showSuccess('Агент создан. Каналы и документы можно подключить позже.');
      if (projectIdFromQuery) {
        navigate(NAVIGATION_ROUTES.PROJECT_AGENTS(projectIdFromQuery));
      } else {
        navigate(NAVIGATION_ROUTES.PROJECTS_LIST);
      }
    } catch (error) {
      showError(error.message || 'Не удалось создать агента');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <MainLayout>
      <div className="agent-ai-create-page">
        <div className="agent-ai-create-card">
          <h2>Создание агента с ИИ</h2>
          <p className="agent-ai-create-subtitle">
            Опишите задачу, получите готовый шаблон и системный промпт, затем создайте агента в один клик.
          </p>

          <label htmlFor="agent-ai-brief">Что должен делать агент?</label>
          <textarea
            id="agent-ai-brief"
            className="input-main textarea"
            rows={5}
            placeholder="Например: агент для первичной квалификации заявок с сайта и в Telegram, задает 5 вопросов, собирает контакты и передает менеджеру."
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            maxLength={1200}
          />
          <div className="agent-ai-create-meta">{brief.length} / 1200</div>

          <label htmlFor="agent-ai-context">Контекст проекта (опционально)</label>
          <input
            id="agent-ai-context"
            type="text"
            className="input-main"
            placeholder="Например: стоматология, Москва"
            value={projectContext}
            onChange={(e) => setProjectContext(e.target.value)}
            maxLength={200}
          />

          <div className="agent-ai-create-actions">
            <button
              type="button"
              className="btn btn-black"
              onClick={handleGenerate}
              disabled={isGenerating || !briefValid}
            >
              {isGenerating ? 'Генерируем...' : 'Сгенерировать'}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => navigate(`${NAVIGATION_ROUTES.CREATE_AGENT}${projectIdFromQuery ? `?projectId=${projectIdFromQuery}` : ''}`)}
            >
              Вручную
            </button>
          </div>
        </div>

        {draft ? (
          <div className="agent-ai-create-card">
            <h3>Предпросмотр</h3>
            <label htmlFor="agent-ai-name">Название</label>
            <input
              id="agent-ai-name"
              type="text"
              className="input-main"
              value={draft.suggested_name || ''}
              onChange={(e) => handleDraftChange('suggested_name', e.target.value)}
              maxLength={100}
            />

            <label htmlFor="agent-ai-template">Шаблон</label>
            <CustomSelect
              id="agent-ai-template"
              name="agent-ai-template"
              value={draft.template_type || 'qa'}
              onChange={(e) => handleDraftChange('template_type', e.target.value)}
              options={TEMPLATE_OPTIONS}
            />

            <label htmlFor="agent-ai-system-prompt">Системный промпт</label>
            <textarea
              id="agent-ai-system-prompt"
              className="input-main textarea"
              rows={10}
              value={draft.system_prompt || ''}
              onChange={(e) => handleDraftChange('system_prompt', e.target.value)}
              maxLength={5000}
            />

            <label htmlFor="agent-ai-welcome">Приветствие</label>
            <textarea
              id="agent-ai-welcome"
              className="input-main textarea"
              rows={3}
              value={draft.welcome_message || ''}
              onChange={(e) => handleDraftChange('welcome_message', e.target.value)}
              maxLength={500}
            />

            <div className="agent-ai-create-actions">
              <button
                type="button"
                className="btn btn-black"
                onClick={handleCreate}
                disabled={isCreating || !(draft.system_prompt || '').trim()}
              >
                {isCreating ? 'Создаем...' : 'Создать агента'}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </MainLayout>
  );
};

export default AgentCreateAiPage;
