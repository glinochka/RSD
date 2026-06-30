/**
 * Project Website Page
 * Website management dashboard for project
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import { NAVIGATION_ROUTES } from '../../config/constants';
import projectService from '../../services/projectService';
import websiteService from '../../services/websiteService';
import '../../styles/projectWebsitePage.css';

// Icons
const GlobeIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const EditIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
  </svg>
);

const ExternalLinkIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </svg>
);

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const SpinnerIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spinner-animation">
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
    draft: 'Черновик',
    published: 'Опубликован',
    archived: 'В архиве',
  };
  return labels[status] || status;
};

const getGenerationStatusLabel = (status) => {
  const labels = {
    idle: 'Ожидание',
    queued: 'В очереди',
    generating: 'Генерация...',
    completed: 'Готово',
    failed: 'Ошибка',
  };
  return labels[status] || status;
};

const ProjectWebsitePage = () => {
  const { projectId } = useParams();
  const { showError, showSuccess } = useNotification();

  const [website, setWebsite] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    loadWebsite();
    loadAgents();
  }, [projectId]);

  const loadWebsite = async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProjectWebsite(projectId);
      setWebsite(data);
    } catch (error) {
      console.error('Failed to load website:', error);
      // No website is OK - show "create" CTA
      setWebsite(null);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const data = await projectService.getProjectAgents(projectId);
      setAgents(data || []);
    } catch (error) {
      console.error('Failed to load agents:', error);
    }
  };

  const handleCreateWebsite = async (agentId) => {
    try {
      const newWebsite = await websiteService.create({
        agent_id: agentId,
        project_id: projectId,
        title: 'Новый сайт',
      });
      showSuccess('Сайт создан и генерируется');
      setWebsite(newWebsite);
    } catch (error) {
      console.error('Failed to create website:', error);
      showError('Не удалось создать сайт');
    }
  };

  if (isLoading) {
    return (
      <div className="project-website-page project-website-page--loading">
        <div className="website-loading">
          <div className="spinner" />
          <p>Загрузка данных сайта...</p>
        </div>
      </div>
    );
  }

  // No website - show create CTA
  if (!website) {
    return (
      <div className="project-website-page">
        <div className="website-header">
          <div>
            <h2 className="website-title">Сайт проекта</h2>
            <p className="website-subtitle">Создайте сайт для вашего бизнеса</p>
          </div>
        </div>

        <div className="website-empty">
          <div className="website-empty-icon">
            <GlobeIcon />
          </div>
          <h3 className="website-empty-title">Сайт еще не создан</h3>
          <p className="website-empty-description">
            Создайте сайт и свяжите его с одним из агентов проекта
          </p>

          {agents.length > 0 ? (
            <div className="website-agent-select">
              <h4>Выберите агента для сайта:</h4>
              <div className="website-agent-list">
                {agents.map((agent) => (
                  <button
                    key={agent.id}
                    type="button"
                    className="website-agent-option"
                    onClick={() => handleCreateWebsite(agent.id)}
                  >
                    <span className="website-agent-name">
                      {agent.bot_username || `Агент #${agent.id}`}
                    </span>
                    <span className="website-agent-type">
                      {agent.template_type}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="website-no-agents">
              <p>Сначала создайте агента для проекта</p>
              <Link to={NAVIGATION_ROUTES.PROJECT_AGENTS(projectId)} className="btn btn-black">
                Перейти к агентам
              </Link>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Website exists - show status and actions
  return (
    <div className="project-website-page">
      <div className="website-header">
        <div>
          <h2 className="website-title">{website.title || 'Сайт проекта'}</h2>
          <p className="website-subtitle">
            Статус: <span className={`website-status-badge website-status--${website.status}`}>
              {getStatusLabel(website.status)}
            </span>
            {website.generation_status && website.generation_status !== 'idle' && (
              <span className={`website-gen-status website-gen-status--${website.generation_status}`}>
                {getGenerationStatusLabel(website.generation_status)}
              </span>
            )}
          </p>
        </div>
        <div className="website-actions">
          <Link
            to={NAVIGATION_ROUTES.WEBSITE_EDITOR(website.id)}
            className="btn btn-black"
          >
            <EditIcon />
            Редактировать
          </Link>
          {website.status === 'published' && website.slug && (
            <a
              href={`/w/${website.slug}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-outline"
            >
              <ExternalLinkIcon />
              Открыть сайт
            </a>
          )}
        </div>
      </div>

      <div className="website-info-grid">
        <div className="website-info-card">
          <h4>URL сайта</h4>
          {website.slug ? (
            <div className="website-url">
              <code>/w/{website.slug}</code>
              <a
                href={`/w/${website.slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="website-url-link"
              >
                <ExternalLinkIcon />
              </a>
            </div>
          ) : (
            <p className="website-url-not-set">URL не назначен</p>
          )}
        </div>

        <div className="website-info-card">
          <h4>Генерация</h4>
          <p className={`website-gen-status website-gen-status--${website.generation_status || 'idle'}`}>
            {website.generation_status === 'generating' && <SpinnerIcon />}
            {getGenerationStatusLabel(website.generation_status || 'idle')}
          </p>
        </div>

        <div className="website-info-card">
          <h4>Связанный агент</h4>
          <p className="website-agent-link">
            {website.agent_id ? (
              <Link to={NAVIGATION_ROUTES.EDIT_AGENT(website.agent_id)}>
                Агент #{website.agent_id}
              </Link>
            ) : (
              'Не назначен'
            )}
          </p>
        </div>

        <div className="website-info-card">
          <h4>Создан</h4>
          <p className="website-date">
            {new Date(website.created_at).toLocaleDateString('ru-RU')}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProjectWebsitePage;
