/**
 * Project Dashboard Page
 * Main dashboard for project overview with widgets and onboarding checklist
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import projectService from '../../services/projectService';
import { NAVIGATION_ROUTES } from '../../config/constants';
import { useNotification } from '../../context/useNotification';
import '../../styles/projectDashboard.css';

// Icons
const BotIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
  </svg>
);

const GlobeIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const MessageIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const UsersIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const CircleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
  </svg>
);

const ArrowRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </svg>
);

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const FileIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const EditIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
  </svg>
);

const ProjectDashboardPage = () => {
  const { projectId } = useParams();
  const { showError } = useNotification();

  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setIsLoading(true);
        const dashboardData = await projectService.getProjectDashboard(projectId);
        setData(dashboardData);
      } catch (error) {
        console.error('Failed to load dashboard:', error);
        showError('Не удалось загрузить данные дашборда');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboard();
  }, [projectId, showError]);

  if (isLoading) {
    return (
      <div className="project-dashboard project-dashboard--loading">
        <div className="dashboard-loading">
          <div className="dashboard-spinner" />
          <p>Загрузка дашборда...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="project-dashboard">
        <div className="dashboard-error">
          <p>Не удалось загрузить данные</p>
        </div>
      </div>
    );
  }

  const { project, summary, onboarding_checklist, quick_actions } = data;
  const completedTasks = onboarding_checklist.filter((t) => t.completed).length;
  const totalTasks = onboarding_checklist.length;

  return (
    <div className="project-dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div className="dashboard-header-content">
          <h1 className="dashboard-title">{project.name}</h1>
          <p className="dashboard-subtitle">
            {project.industry && (
              <span className="dashboard-industry">{project.industry}</span>
            )}
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="dashboard-stats-grid">
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-icon dashboard-stat-icon--agents">
            <BotIcon />
          </div>
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{summary.agents_total}</span>
            <span className="dashboard-stat-label">
              {summary.agents_active > 0 ? `${summary.agents_active} активных` : 'Агентов'}
            </span>
          </div>
        </div>

        <div className="dashboard-stat-card">
          <div className="dashboard-stat-icon dashboard-stat-icon--dialogs">
            <MessageIcon />
          </div>
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{summary.dialogs_7d}</span>
            <span className="dashboard-stat-label">Диалогов за 7 дней</span>
          </div>
        </div>

        <div className="dashboard-stat-card">
          <div className="dashboard-stat-icon dashboard-stat-icon--leads">
            <UsersIcon />
          </div>
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{summary.new_leads_7d}</span>
            <span className="dashboard-stat-label">Новых лидов</span>
          </div>
        </div>

        <div className={`dashboard-stat-card ${summary.website_status === 'published' ? 'dashboard-stat-card--success' : ''}`}>
          <div className="dashboard-stat-icon dashboard-stat-icon--website">
            <GlobeIcon />
          </div>
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">
              {summary.website_status === 'published' ? 'Онлайн' : 'Не опубликован'}
            </span>
            <span className="dashboard-stat-label">Сайт</span>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Onboarding Checklist */}
        <div className="dashboard-section dashboard-section--checklist">
          <div className="dashboard-section-header">
            <h2 className="dashboard-section-title">
              Чеклист запуска
              <span className="dashboard-section-badge">
                {completedTasks}/{totalTasks}
              </span>
            </h2>
          </div>

          <div className="dashboard-checklist">
            {onboarding_checklist.map((item) => (
              <div
                key={item.id}
                className={`dashboard-checklist-item ${item.completed ? 'dashboard-checklist-item--completed' : ''}`}
              >
                <div className="dashboard-checklist-icon">
                  {item.completed ? <CheckIcon /> : <CircleIcon />}
                </div>
                <span className="dashboard-checklist-label">{item.label}</span>
                {!item.completed && item.action_url && (
                  <Link to={item.action_url} className="dashboard-checklist-action">
                    Выполнить
                    <ArrowRightIcon />
                  </Link>
                )}
              </div>
            ))}
          </div>

          {completedTasks === totalTasks && (
            <div className="dashboard-checklist-complete">
              <CheckIcon />
              <span>Все задачи выполнены! Проект готов к работе.</span>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="dashboard-section dashboard-section--actions">
          <div className="dashboard-section-header">
            <h2 className="dashboard-section-title">Быстрые действия</h2>
          </div>

          <div className="dashboard-actions">
            {quick_actions.map((action) => (
              <Link
                key={action.id}
                to={action.url}
                className="dashboard-action-card"
              >
                <div className="dashboard-action-icon">
                  {action.icon === 'bot' && <BotIcon />}
                  {action.icon === 'file' && <FileIcon />}
                  {action.icon === 'globe' && <GlobeIcon />}
                </div>
                <span className="dashboard-action-label">{action.label}</span>
                <ArrowRightIcon />
              </Link>
            ))}

            {/* Add Agent Action */}
            <Link
              to={NAVIGATION_ROUTES.PROJECT_AGENTS(projectId)}
              className="dashboard-action-card dashboard-action-card--add"
            >
              <div className="dashboard-action-icon">
                <PlusIcon />
              </div>
              <span className="dashboard-action-label">Добавить агента</span>
              <ArrowRightIcon />
            </Link>

            {/* Upload Knowledge Action */}
            <Link
              to={NAVIGATION_ROUTES.PROJECT_KNOWLEDGE(projectId)}
              className="dashboard-action-card dashboard-action-card--add"
            >
              <div className="dashboard-action-icon">
                <FileIcon />
              </div>
              <span className="dashboard-action-label">Загрузить документ</span>
              <ArrowRightIcon />
            </Link>
          </div>
        </div>
      </div>

      {/* Website Status Card */}
      {summary.website_status && (
        <div className="dashboard-website-card">
          <div className="dashboard-website-info">
            <GlobeIcon />
            <div>
              <h3>Статус сайта</h3>
              <p>
                {summary.website_status === 'published'
                  ? `Сайт опубликован: ${summary.website_url}`
                  : 'Сайт находится в разработке'}
              </p>
            </div>
          </div>
          {summary.website_url && (
            <a
              href={summary.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-outline"
            >
              Открыть сайт
            </a>
          )}
        </div>
      )}
    </div>
  );
};

export default ProjectDashboardPage;
