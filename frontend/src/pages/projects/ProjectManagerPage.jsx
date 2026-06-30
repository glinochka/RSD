/**
 * Project AI Manager Page
 * AI Manager (MOP) dashboard for project
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import { useAuth } from '../../context/useAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';
import projectService from '../../services/projectService';
import '../../styles/projectManagerPage.css';

// Icons
const BriefcaseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

const TrendingUpIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
    <polyline points="17 6 23 6 23 12" />
  </svg>
);

const MessageSquareIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const TargetIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const SparklesIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
  </svg>
);

const ProjectManagerPage = () => {
  const { projectId } = useParams();
  const { showError } = useNotification();
  const { user } = useAuth();

  const [agents, setAgents] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAiMopEnabled, setIsAiMopEnabled] = useState(false);

  useEffect(() => {
    loadManagerData();
    checkAiMopEnabled();
  }, [projectId]);

  const loadManagerData = async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProjectAiManager(projectId);
      setAgents(data.agents || []);
      setAnalytics(data.analytics);
    } catch (error) {
      console.error('Failed to load AI manager data:', error);
      showError('Не удалось загрузить данные');
    } finally {
      setIsLoading(false);
    }
  };

  const checkAiMopEnabled = async () => {
    // Check feature flag from environment or API
    try {
      const settings = await projectService.getSettings();
      setIsAiMopEnabled(settings.AI_MOP_ENABLED || false);
    } catch (error) {
      console.error('Failed to check AI MOP flag:', error);
    }
  };

  const hasAiManager = agents.length > 0;
  const isProjectOwner = user?.id === agents[0]?.user_id;

  if (isLoading) {
    return (
      <div className="project-manager-page project-manager-page--loading">
        <div className="manager-loading">
          <div className="spinner" />
          <p>Загрузка данных...</p>
        </div>
      </div>
    );
  }

  // No AI Manager - show CTA
  if (!hasAiManager) {
    return (
      <div className="project-manager-page">
        <div className="manager-header">
          <div>
            <h2 className="manager-title">ИИ-менеджер</h2>
            <p className="manager-subtitle">Умное управление бизнесом с помощью ИИ</p>
          </div>
        </div>

        <div className="manager-empty">
          <div className="manager-empty-icon">
            <BriefcaseIcon />
          </div>
          <h3 className="manager-empty-title">ИИ-менеджер не подключен</h3>
          <p className="manager-empty-description">
            ИИ-менеджер помогает анализировать данные, ставить задачи агентам
            и принимать решения на основе данных проекта
          </p>
          <Link
            to={`${NAVIGATION_ROUTES.CREATE_AGENT}?projectId=${projectId}&template=ai_manager`}
            className="btn btn-black"
          >
            <PlusIcon />
            Добавить ИИ-менеджера
          </Link>
        </div>
      </div>
    );
  }

  // Has AI Manager but MOP not enabled
  if (!isAiMopEnabled) {
    return (
      <div className="project-manager-page">
        <div className="manager-header">
          <div>
            <h2 className="manager-title">ИИ-менеджер</h2>
            <p className="manager-subtitle">Агент подключен</p>
          </div>
        </div>

        <div className="manager-coming-soon">
          <div className="manager-coming-soon-icon">
            <SparklesIcon />
          </div>
          <h3 className="manager-coming-soon-title">В разработке</h3>
          <p className="manager-coming-soon-description">
            Функционал управления через ИИ-менеджера будет доступен в ближайшем обновлении
          </p>
        </div>
      </div>
    );
  }

  // Full AI Manager dashboard (for project owner)
  return (
    <div className="project-manager-page">
      <div className="manager-header">
        <div>
          <h2 className="manager-title">ИИ-менеджер</h2>
          <p className="manager-subtitle">Управление проектом с помощью ИИ</p>
        </div>
        <div className="manager-actions">
          {agents.map((agent) => (
            <Link
              key={agent.id}
              to={NAVIGATION_ROUTES.EDIT_AGENT(agent.id)}
              className="btn btn-outline"
            >
              Настройки агента
            </Link>
          ))}
        </div>
      </div>

      {/* Analytics Dashboard */}
      <div className="manager-analytics-grid">
        <div className="manager-analytics-card">
          <div className="manager-analytics-icon manager-analytics-icon--blue">
            <TrendingUpIcon />
          </div>
          <div className="manager-analytics-info">
            <span className="manager-analytics-value">{analytics?.conversions || 0}</span>
            <span className="manager-analytics-label">Конверсии</span>
          </div>
        </div>

        <div className="manager-analytics-card">
          <div className="manager-analytics-icon manager-analytics-icon--green">
            <MessageSquareIcon />
          </div>
          <div className="manager-analytics-info">
            <span className="manager-analytics-value">{analytics?.messages || 0}</span>
            <span className="manager-analytics-label">Сообщений</span>
          </div>
        </div>

        <div className="manager-analytics-card">
          <div className="manager-analytics-icon manager-analytics-icon--purple">
            <TargetIcon />
          </div>
          <div className="manager-analytics-info">
            <span className="manager-analytics-value">{analytics?.goals || 0}</span>
            <span className="manager-analytics-label">Целей достигнуто</span>
          </div>
        </div>
      </div>

      {/* Agents List */}
      <div className="manager-section">
        <h3 className="manager-section-title">Подключенные агенты</h3>
        <div className="manager-agents-list">
          {agents.map((agent) => (
            <div key={agent.id} className="manager-agent-card">
              <div className="manager-agent-icon">
                <BriefcaseIcon />
              </div>
              <div className="manager-agent-info">
                <h4 className="manager-agent-name">
                  {agent.bot_username || `Агент #${agent.id}`}
                </h4>
                <p className="manager-agent-status">
                  {agent.is_active ? 'Активен' : 'Неактивен'}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Owner-only features */}
      {isProjectOwner && (
        <div className="manager-owner-panel">
          <h3 className="manager-section-title">Управление</h3>
          <p className="manager-owner-description">
            Дополнительные инструменты управления доступны в панели владельца
          </p>
          <div className="manager-owner-actions">
            <button type="button" className="btn btn-outline" disabled>
              Сгенерировать отчет
            </button>
            <button type="button" className="btn btn-outline" disabled>
              Установить цели
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectManagerPage;
