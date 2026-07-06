/**
 * Project Dashboard Page
 * Main dashboard for project overview with widgets, charts and onboarding checklist.
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

const SparklesIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
  </svg>
);

const CloseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const ActivityChart = ({ title, labels, messages, leads }) => {
  const maxValue = Math.max(1, ...messages, ...leads);

  return (
    <div className="dashboard-chart">
      <h3 className="dashboard-chart-title">{title}</h3>
      <div className="dashboard-hchart">
        {labels.map((label, index) => (
          <div key={label} className="dashboard-hchart-row">
            <span className="dashboard-hchart-label">{label}</span>
            <div className="dashboard-hchart-bars">
              <div className="dashboard-hchart-bar-track" title={`Диалоги: ${messages[index]}`}>
                <div className="dashboard-hchart-bar-fill">
                  <div
                    className="dashboard-hchart-bar dashboard-hchart-bar--messages"
                    style={{ width: `${(messages[index] / maxValue) * 100}%` }}
                  />
                </div>
                <span className="dashboard-hchart-value">{messages[index]}</span>
              </div>
              <div className="dashboard-hchart-bar-track" title={`Лиды: ${leads[index]}`}>
                <div className="dashboard-hchart-bar-fill">
                  <div
                    className="dashboard-hchart-bar dashboard-hchart-bar--leads"
                    style={{ width: `${(leads[index] / maxValue) * 100}%` }}
                  />
                </div>
                <span className="dashboard-hchart-value">{leads[index]}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="dashboard-chart-legend">
        <span className="dashboard-chart-legend-item">
          <span className="dashboard-chart-legend-dot dashboard-chart-legend-dot--messages" />
          Диалоги
        </span>
        <span className="dashboard-chart-legend-item">
          <span className="dashboard-chart-legend-dot dashboard-chart-legend-dot--leads" />
          Лиды
        </span>
      </div>
    </div>
  );
};

const MetricChart = ({ title, labels, values }) => {
  const maxValue = Math.max(1, ...values);
  const colors = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b'];

  return (
    <div className="dashboard-chart">
      <h3 className="dashboard-chart-title">{title}</h3>
      <div className="dashboard-hchart dashboard-hchart--metrics">
        {labels.map((label, index) => (
          <div key={label} className="dashboard-hchart-row">
            <span className="dashboard-hchart-label dashboard-hchart-label--wide">{label}</span>
            <div className="dashboard-hchart-bars">
              <div className="dashboard-hchart-bar-track dashboard-hchart-bar-track--single">
                <div className="dashboard-hchart-bar-fill">
                  <div
                    className="dashboard-hchart-bar"
                    style={{
                      width: `${(values[index] / maxValue) * 100}%`,
                      background: colors[index % colors.length],
                    }}
                  />
                </div>
                <span className="dashboard-hchart-value">{values[index]}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const ProjectDashboardPage = () => {
  const { projectId } = useParams();
  const { showError, showSuccess } = useNotification();

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

  const hideChecklist = async () => {
    try {
      await projectService.updateProjectChecklistVisibility(projectId, true);
      setData((prev) => (prev ? { ...prev, checklist_hidden: true } : prev));
      showSuccess('Чеклист скрыт. Вы можете вернуть его в настройках.');
    } catch (error) {
      console.error('Failed to hide checklist:', error);
      showError('Не удалось скрыть чеклист');
    }
  };

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

  const {
    project,
    summary,
    onboarding_checklist,
    checklist_hidden,
    quick_actions,
    charts,
    ai_manager,
  } = data;
  const completedTasks = onboarding_checklist.filter((t) => t.completed).length;
  const totalTasks = onboarding_checklist.length;

  const quickActionsBlock = (
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
      </div>
    </div>
  );

  const aiManagerBlock = (
    <div className="dashboard-section dashboard-section--ai-manager dashboard-section--compact">
      <div className="dashboard-section-header">
        <h2 className="dashboard-section-title">
          <SparklesIcon />
          ИИ-менеджер
        </h2>
      </div>
      <div className="dashboard-ai-manager">
        <p className="dashboard-ai-manager-text">
          {ai_manager?.hint || 'Спросите про лиды, рост и статус проекта.'}
        </p>
        <Link
          to={NAVIGATION_ROUTES.PROJECT_MANAGER(projectId)}
          className="btn btn-black dashboard-ai-manager-btn"
        >
          <SparklesIcon />
          Открыть чат
        </Link>
      </div>
    </div>
  );

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

      <div className={`dashboard-grid dashboard-grid--top ${checklist_hidden ? 'dashboard-grid--top-no-checklist' : ''}`}>
        {!checklist_hidden && (
          <div className="dashboard-section dashboard-section--checklist">
            <div className="dashboard-section-header">
              <h2 className="dashboard-section-title">
                Чеклист запуска
                <span className="dashboard-section-badge">
                  {completedTasks}/{totalTasks}
                </span>
              </h2>
              <button
                type="button"
                className="dashboard-checklist-close"
                onClick={hideChecklist}
                title="Скрыть чеклист навсегда"
              >
                <CloseIcon />
              </button>
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
        )}

        {checklist_hidden ? (
          <>
            {quickActionsBlock}
            {aiManagerBlock}
          </>
        ) : (
          <div className="dashboard-top-right">
            {quickActionsBlock}
            {aiManagerBlock}
          </div>
        )}
      </div>

      <div className="dashboard-section dashboard-section--charts">
        <div className="dashboard-section-header">
          <h2 className="dashboard-section-title">Рост и эффективность</h2>
        </div>
        <div className="dashboard-charts-grid">
          {charts?.growth && (
            <ActivityChart
              title="Активность за 7 дней"
              labels={charts.growth.labels}
              messages={charts.growth.messages}
              leads={charts.growth.leads}
            />
          )}
          {charts?.efficiency && (
            <MetricChart
              title="Эффективность проекта"
              labels={charts.efficiency.labels}
              values={charts.efficiency.values}
            />
          )}
        </div>
      </div>

      {/* Website Status Card */}
      {summary.website_url && (
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
          <a
            href={summary.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-outline"
          >
            Открыть сайт
          </a>
        </div>
      )}
    </div>
  );
};

export default ProjectDashboardPage;
