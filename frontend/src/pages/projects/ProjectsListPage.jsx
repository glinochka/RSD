/**
 * Tools List Page
 * Displays AI agents and websites as separate tools
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../../components/Layout';
import Loading from '../../components/Loading';
import CreateChoiceModal from '../../components/CreateChoiceModal';
import { useAuth } from '../../context/useAuth';
import { useNotification } from '../../context/useNotification';
import agentService from '../../services/agentService';
import websiteService from '../../services/websiteService';
import { NAVIGATION_ROUTES } from '../../config/constants';
import '../../styles/projectsListPage.css';

const PlusIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

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

const EmptyStateIcon = () => (
  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />
  </svg>
);

const ProjectsListPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError } = useNotification();

  const [agents, setAgents] = useState([]);
  const [websites, setWebsites] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateChoiceOpen, setIsCreateChoiceOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const fetchTools = async () => {
      try {
        setIsLoading(true);
        const [agentsResponse, websitesResponse] = await Promise.all([
          agentService.getAll(),
          websiteService.list({ page: 1, page_size: 100 }),
        ]);
        setAgents(Array.isArray(agentsResponse) ? agentsResponse : []);
        setWebsites(Array.isArray(websitesResponse?.items) ? websitesResponse.items : []);
      } catch (error) {
        console.error('Failed to load tools:', error);
        showError(error.message || 'Не удалось загрузить инструменты');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTools();
  }, [isAuthenticated, showError]);

  const formatDate = (dateString) => {
    if (!dateString) return 'Дата не указана';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const handleOpenAgent = () => {
    navigate(NAVIGATION_ROUTES.AGENTS);
  };

  const handleOpenWebsite = (website) => {
    if (!website?.id) return;
    navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(website.id));
  };

  const totalTools = agents.length + websites.length;

  if (!isLoading && totalTools === 0) {
    return (
      <MainLayout>
        <div className="projects-page">
          <div className="projects-empty-state">
            <div className="projects-empty-icon">
              <EmptyStateIcon />
            </div>
            <h2 className="projects-empty-title">У вас пока нет инструментов</h2>
            <p className="projects-empty-description">
              Создайте первый инструмент: отдельный ИИ-агент, сайт или проект.
            </p>
            <button
              type="button"
              className="btn btn-black"
              onClick={() => setIsCreateChoiceOpen(true)}
            >
              <PlusIcon />
              Новый инструмент
            </button>
          </div>
          <CreateChoiceModal
            isOpen={isCreateChoiceOpen}
            onClose={() => setIsCreateChoiceOpen(false)}
          />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="projects-page">
        <div className="projects-header">
          <div className="projects-header-content">
            <h1 className="projects-title">Мои инструменты</h1>
            <p className="projects-subtitle">
              ИИ-агенты и сайты в одном месте
            </p>
          </div>
          <button
            type="button"
            className="btn btn-black"
            onClick={() => setIsCreateChoiceOpen(true)}
          >
            <PlusIcon />
            Новый инструмент
          </button>
        </div>

        {isLoading ? (
          <div className="projects-loading">
            <Loading />
            <p>Загрузка инструментов...</p>
          </div>
        ) : (
          <div className="projects-grid">
            {agents.map((agent) => (
              <div
                key={`agent-${agent.id}`}
                className="project-card"
                onClick={handleOpenAgent}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    handleOpenAgent();
                  }
                }}
              >
                <div className="project-card-header">
                  <div className="project-card-icon">
                    <BotIcon />
                  </div>
                  <div className="project-card-meta">
                    <span className="project-card-date">
                      {formatDate(agent.created_at)}
                    </span>
                    <span className="project-card-badge project-card-badge--default">
                      ИИ-агент
                    </span>
                  </div>
                </div>

                <div className="project-card-content">
                  <h3 className="project-card-name">
                    {agent.bot_username ? `@${agent.bot_username}` : `Агент #${agent.id}`}
                  </h3>
                  <p className="project-card-industry">
                    {agent.template_type || 'assistant'}
                  </p>
                  <p className="project-card-description">
                    {agent.is_active ? 'Активен и готов к работе' : 'Отключен'}
                  </p>
                </div>
              </div>
            ))}

            {websites.map((website) => (
              <div
                key={`website-${website.id}`}
                className="project-card"
                onClick={() => handleOpenWebsite(website)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    handleOpenWebsite(website);
                  }
                }}
              >
                <div className="project-card-header">
                  <div className="project-card-icon">
                    <GlobeIcon />
                  </div>
                  <div className="project-card-meta">
                    <span className="project-card-date">
                      {formatDate(website.created_at)}
                    </span>
                    <span className="project-card-badge project-card-badge--default">
                      Сайт
                    </span>
                  </div>
                </div>

                <div className="project-card-content">
                  <h3 className="project-card-name">{website.title || `Сайт #${website.id}`}</h3>
                  <p className="project-card-industry">/{website.slug}</p>
                  <p className="project-card-description">
                    {website.status === 'published'
                      ? 'Опубликован'
                      : website.generation_status === 'queued' || website.generation_status === 'generating'
                        ? 'Генерируется'
                        : 'Черновик'}
                  </p>
                </div>
              </div>
            ))}

            <div
              className="project-card project-card--add"
              onClick={() => setIsCreateChoiceOpen(true)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  setIsCreateChoiceOpen(true);
                }
              }}
            >
              <div className="project-card-add-content">
                <div className="project-card-add-icon">
                  <PlusIcon />
                </div>
                <p className="project-card-add-text">Создать новый инструмент</p>
              </div>
            </div>
          </div>
        )}
      </div>

      <CreateChoiceModal
        isOpen={isCreateChoiceOpen}
        onClose={() => setIsCreateChoiceOpen(false)}
      />
    </MainLayout>
  );
};

export default ProjectsListPage;
