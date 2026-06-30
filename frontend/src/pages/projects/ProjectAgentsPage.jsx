/**
 * Project Agents Page
 * Agents management within project context
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import { NAVIGATION_ROUTES } from '../../config/constants';
import CreateChoiceModal from '../../components/CreateChoiceModal';
import agentService from '../../services/agentService';
import '../../styles/projectAgentsPage.css';

// Icons
const BotIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
  </svg>
);

const PlusIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const ChartIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const EmptyStateIcon = () => (
  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
    <line x1="8" y1="16" x2="8" y2="16" />
    <line x1="16" y1="16" x2="16" y2="16" />
  </svg>
);

// Template type labels
const TEMPLATE_LABELS = {
  qa: 'Вопрос-ответ',
  crm_admin: 'Запись клиентов',
  sales_manager: 'Продажи',
  content_factory: 'Контент',
  ai_manager: 'ИИ-менеджер',
};

const ProjectAgentsPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { showError } = useNotification();

  const [agents, setAgents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  useEffect(() => {
    loadAgents();
  }, [projectId]);

  const loadAgents = async () => {
    try {
      setIsLoading(true);
      const data = await agentService.getAgentsByProject(projectId);
      setAgents(data);
    } catch (error) {
      console.error('Failed to load agents:', error);
      showError('Не удалось загрузить агентов');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddAgent = () => {
    navigate(`${NAVIGATION_ROUTES.CREATE_AGENT}?projectId=${projectId}`);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  // Empty state
  if (!isLoading && agents.length === 0) {
    return (
      <div className="project-agents-page">
        <div className="project-agents-header">
          <h2 className="project-agents-title">Агенты проекта</h2>
          <button
            type="button"
            className="btn btn-black"
            onClick={handleAddAgent}
          >
            <PlusIcon />
            Добавить агента
          </button>
        </div>

        <div className="project-agents-empty">
          <div className="project-agents-empty-icon">
            <EmptyStateIcon />
          </div>
          <h3 className="project-agents-empty-title">В проекте пока нет агентов</h3>
          <p className="project-agents-empty-description">
            Создайте первого ИИ-агента для автоматизации общения с клиентами
          </p>
          <button
            type="button"
            className="btn btn-black"
            onClick={handleAddAgent}
          >
            <PlusIcon />
            Создать агента
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="project-agents-page">
      <div className="project-agents-header">
        <h2 className="project-agents-title">
          Агенты проекта
          <span className="project-agents-count">{agents.length}</span>
        </h2>
        <button
          type="button"
          className="btn btn-black"
          onClick={handleAddAgent}
        >
          <PlusIcon />
          Добавить агента
        </button>
      </div>

      {isLoading ? (
        <div className="project-agents-loading">
          <div className="spinner" />
          <p>Загрузка агентов...</p>
        </div>
      ) : (
        <div className="project-agents-list">
          {agents.map((agent) => (
            <div key={agent.id} className="project-agent-card">
              <div className="project-agent-card-header">
                <div className={`project-agent-status ${agent.is_active ? 'project-agent-status--active' : 'project-agent-status--inactive'}`}>
                  {agent.is_active ? 'Активен' : 'Неактивен'}
                </div>
                <span className="project-agent-template">
                  {TEMPLATE_LABELS[agent.template_type] || agent.template_type}
                </span>
              </div>

              <div className="project-agent-card-body">
                <div className="project-agent-icon">
                  <BotIcon />
                </div>
                <div className="project-agent-info">
                  <h3 className="project-agent-name">
                    {agent.bot_username || `Агент #${agent.id}`}
                  </h3>
                  <p className="project-agent-id">ID: {agent.bot_id || agent.id}</p>
                  <p className="project-agent-date">
                    Создан: {formatDate(agent.registered)}
                  </p>
                </div>
              </div>

              <div className="project-agent-card-footer">
                <Link
                  to={NAVIGATION_ROUTES.AGENT_ANALYTICS(agent.id)}
                  className="project-agent-action"
                >
                  <ChartIcon />
                  <span>Аналитика</span>
                </Link>
                <Link
                  to={NAVIGATION_ROUTES.EDIT_AGENT(agent.id)}
                  className="project-agent-action"
                >
                  <SettingsIcon />
                  <span>Настройки</span>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ProjectAgentsPage;
