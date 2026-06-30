/**
 * Project Content Factory Page
 * Content automation dashboard for project
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import { NAVIGATION_ROUTES } from '../../config/constants';
import projectService from '../../services/projectService';
import '../../styles/projectContentPage.css';

// Icons
const PenToolIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 19l7-7 3 3-7 7-3-3z" />
    <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
    <path d="M2 2l7.586 7.586" />
    <circle cx="11" cy="11" r="2" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const SpinnerIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spinner-animation">
    <line x1="12" y1="2" x2="12" y2="6" />
    <line x1="12" y1="18" x2="12" y2="22" />
    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
    <line x1="2" y1="12" x2="6" y2="12" />
    <line x1="18" y1="12" x2="22" y2="12" />
    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
  </svg>
);

// Status helpers
const getStatusLabel = (status) => {
  const labels = {
    queued: 'В очереди',
    running: 'Выполняется',
    completed: 'Завершено',
    failed: 'Ошибка',
  };
  return labels[status] || status;
};

const ProjectContentPage = () => {
  const { projectId } = useParams();
  const { showError } = useNotification();

  const [agents, setAgents] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadContentData();
  }, [projectId]);

  const loadContentData = async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProjectContentAgents(projectId);
      setAgents(data.agents || []);
      setJobs(data.jobs || []);
    } catch (error) {
      console.error('Failed to load content data:', error);
      showError('Не удалось загрузить данные');
    } finally {
      setIsLoading(false);
    }
  };

  const hasContentFactory = agents.length > 0;
  const activeJobs = jobs.filter((j) => j.status === 'running' || j.status === 'queued');
  const completedJobs = jobs.filter((j) => j.status === 'completed');

  if (isLoading) {
    return (
      <div className="project-content-page project-content-page--loading">
        <div className="content-loading">
          <div className="spinner" />
          <p>Загрузка данных...</p>
        </div>
      </div>
    );
  }

  // No content factory agent - show CTA
  if (!hasContentFactory) {
    return (
      <div className="project-content-page">
        <div className="content-header">
          <div>
            <h2 className="content-title">Контент-завод</h2>
            <p className="content-subtitle">Автоматизация публикаций</p>
          </div>
        </div>

        <div className="content-empty">
          <div className="content-empty-icon">
            <PenToolIcon />
          </div>
          <h3 className="content-empty-title">Контент-завод не подключен</h3>
          <p className="content-empty-description">
            Создайте агента типа &quot;content_factory&quot; для автоматической генерации
            и публикации контента
          </p>
          <Link
            to={`${NAVIGATION_ROUTES.CREATE_AGENT}?projectId=${projectId}&template=content_factory`}
            className="btn btn-black"
          >
            <PlusIcon />
            Добавить контент-завод
          </Link>
        </div>
      </div>
    );
  }

  // Has content factory - show dashboard
  return (
    <div className="project-content-page">
      <div className="content-header">
        <div>
          <h2 className="content-title">Контент-завод</h2>
          <p className="content-subtitle">
            Активных задач: {activeJobs.length} | Всего выполнено: {completedJobs.length}
          </p>
        </div>
        <div className="content-actions">
          {agents.map((agent) => (
            <Link
              key={agent.id}
              to={NAVIGATION_ROUTES.EDIT_AGENT(agent.id)}
              className="btn btn-outline"
            >
              <SettingsIcon />
              Настройки агента
            </Link>
          ))}
        </div>
      </div>

      {/* Agents Section */}
      <div className="content-section">
        <h3 className="content-section-title">Агенты контент-завода</h3>
        <div className="content-agents-list">
          {agents.map((agent) => (
            <div key={agent.id} className="content-agent-card">
              <div className="content-agent-icon">
                <PenToolIcon />
              </div>
              <div className="content-agent-info">
                <h4 className="content-agent-name">
                  {agent.bot_username || `Агент #${agent.id}`}
                </h4>
                <p className="content-agent-status">
                  {agent.is_active ? 'Активен' : 'Неактивен'}
                </p>
              </div>
              <Link
                to={NAVIGATION_ROUTES.EDIT_AGENT(agent.id)}
                className="content-agent-action"
              >
                <SettingsIcon />
              </Link>
            </div>
          ))}
        </div>
      </div>

      {/* Jobs Section */}
      {jobs.length > 0 && (
        <div className="content-section">
          <h3 className="content-section-title">Задачи генерации</h3>
          <div className="content-jobs-list">
            {jobs.slice(0, 10).map((job) => (
              <div key={job.id} className={`content-job-card content-job--${job.status}`}>
                <div className="content-job-status">
                  {job.status === 'running' && <SpinnerIcon />}
                  {getStatusLabel(job.status)}
                </div>
                <div className="content-job-info">
                  <h4 className="content-job-title">{job.title || 'Генерация контента'}</h4>
                  <p className="content-job-date">
                    {new Date(job.created_at).toLocaleString('ru-RU')}
                  </p>
                </div>
                {job.result_url && (
                  <a
                    href={job.result_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="content-job-link"
                  >
                    Открыть
                  </a>
                )}
              </div>
            ))}
          </div>
          {jobs.length > 10 && (
            <p className="content-jobs-more">
              + ещё {jobs.length - 10} задач
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default ProjectContentPage;
