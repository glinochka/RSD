/**
 * Solutions List Page
 * Unified list of projects, agents and websites with right-side quick dashboard
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../../components/Layout';
import Loading from '../../components/Loading';
import CreateChoiceModal from '../../components/CreateChoiceModal';
import { useAuth } from '../../context/useAuth';
import { useNotification } from '../../context/useNotification';
import agentService from '../../services/agentService';
import websiteService from '../../services/websiteService';
import projectService from '../../services/projectService';
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

const BriefcaseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

const ArrowRightIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </svg>
);

const ProjectsListPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError } = useNotification();

  const [projects, setProjects] = useState([]);
  const [agents, setAgents] = useState([]);
  const [websites, setWebsites] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateChoiceOpen, setIsCreateChoiceOpen] = useState(false);
  const [selectedSolution, setSelectedSolution] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedWebsite, setSelectedWebsite] = useState(null);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const [websiteApplications, setWebsiteApplications] = useState([]);
  const [isApplicationsLoading, setIsApplicationsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    const fetchSolutions = async () => {
      try {
        setIsLoading(true);
        const [projectsResponse, agentsResponse, websitesResponse] = await Promise.all([
          projectService.listProjects(),
          agentService.getAll(),
          websiteService.list({ page: 1, page_size: 100 }),
        ]);
        setProjects(Array.isArray(projectsResponse?.items) ? projectsResponse.items : []);
        setAgents(Array.isArray(agentsResponse) ? agentsResponse : []);
        setWebsites(Array.isArray(websitesResponse?.items) ? websitesResponse.items : []);
      } catch (error) {
        console.error('Failed to load solutions:', error);
        showError(error.message || 'Не удалось загрузить решения');
      } finally {
        setIsLoading(false);
      }
    };

    fetchSolutions();
  }, [isAuthenticated, showError]);

  useEffect(() => {
    if (!selectedSolution) {
      setSelectedAgent(null);
      setSelectedWebsite(null);
      setWebsiteApplications([]);
      return;
    }

    const loadDetails = async () => {
      setIsDetailsLoading(true);
      setWebsiteApplications([]);
      try {
        if (selectedSolution.type === 'agent') {
          const agentDetails = await agentService.getById(selectedSolution.id);
          setSelectedAgent(agentDetails || null);
          setSelectedWebsite(null);
          return;
        }
        if (selectedSolution.type === 'website') {
          const websiteDetails = await websiteService.getById(selectedSolution.id);
          setSelectedWebsite(websiteDetails || null);
          setSelectedAgent(null);
          return;
        }
      } catch (error) {
        showError(error?.message || 'Не удалось загрузить детали');
        setSelectedAgent(null);
        setSelectedWebsite(null);
      } finally {
        setIsDetailsLoading(false);
      }
    };

    loadDetails();
  }, [selectedSolution, showError]);

  useEffect(() => {
    if (!selectedWebsite?.agent_id) {
      setWebsiteApplications([]);
      return;
    }

    let cancelled = false;
    const loadApplications = async () => {
      setIsApplicationsLoading(true);
      try {
        const response = await agentService.listAdminTemplateApplications({
          agent_id: selectedWebsite.agent_id,
          limit: 20,
          offset: 0,
        });
        if (cancelled) {
          return;
        }
        setWebsiteApplications(Array.isArray(response?.items) ? response.items : []);
      } catch (error) {
        if (!cancelled) {
          showError(error?.message || 'Не удалось загрузить заявки сайта');
        }
      } finally {
        if (!cancelled) {
          setIsApplicationsLoading(false);
        }
      }
    };

    loadApplications();
    return () => {
      cancelled = true;
    };
  }, [selectedWebsite?.agent_id, showError]);

  const formatDate = (dateString) => {
    if (!dateString) {
      return 'Дата не указана';
    }
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const onProjectClick = (projectId) => {
    navigate(NAVIGATION_ROUTES.PROJECT_DETAIL(projectId));
  };

  const onAgentClick = (agentId) => {
    setSelectedSolution({ type: 'agent', id: agentId });
  };

  const onWebsiteClick = (websiteId) => {
    setSelectedSolution({ type: 'website', id: websiteId });
  };

  const openAgentManagement = () => {
    navigate(NAVIGATION_ROUTES.AGENTS);
  };

  const openWebsiteEditor = () => {
    if (!selectedWebsite?.id) {
      return;
    }
    navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(selectedWebsite.id));
  };

  const openWebsitePublic = () => {
    if (!selectedWebsite?.slug) {
      return;
    }
    window.open(NAVIGATION_ROUTES.WEBSITE_PUBLIC(selectedWebsite.slug), '_blank', 'noopener,noreferrer');
  };

  const projectItems = projects.map((project) => ({
      id: project.id,
      type: 'project',
      created_at: project.created_at,
      title: project.name || `Проект #${project.id}`,
      subtitle: project.industry || 'Проект',
      description: project.description || 'Открыть пространство проекта',
      badge: 'Проект',
      icon: BriefcaseIcon,
      onClick: () => onProjectClick(project.id),
    }));

  const agentItems = agents.map((agent) => ({
      id: agent.id,
      type: 'agent',
      created_at: agent.created_at,
      title: agent.bot_username ? `@${agent.bot_username}` : `Агент #${agent.id}`,
      subtitle: agent.template_type || 'assistant',
      description: agent.is_active ? 'Активен и готов к работе' : 'Отключен',
      badge: 'ИИ-агент',
      icon: BotIcon,
      onClick: () => onAgentClick(agent.id),
    }));

  const websiteItems = websites.map((website) => ({
      id: website.id,
      type: 'website',
      created_at: website.created_at,
      title: website.title || `Сайт #${website.id}`,
      subtitle: `/${website.slug || 'website'}`,
      description:
        website.status === 'published'
          ? 'Опубликован'
          : website.generation_status === 'queued' || website.generation_status === 'generating'
            ? 'Генерируется'
            : 'Черновик',
      badge: 'Сайт',
      icon: GlobeIcon,
      onClick: () => onWebsiteClick(website.id),
    }));

  const solutions = [...projectItems, ...agentItems, ...websiteItems]
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());

  const totalTools = solutions.length;
  const hasRightPanel = selectedSolution?.type === 'agent' || selectedSolution?.type === 'website';

  if (!isLoading && totalTools === 0) {
    return (
      <MainLayout>
        <div className="projects-page">
          <div className="projects-empty-state">
            <div className="projects-empty-icon">
              <EmptyStateIcon />
            </div>
            <h2 className="projects-empty-title">У вас пока нет решений</h2>
            <p className="projects-empty-description">
              Создайте первое решение: отдельный ИИ-агент, сайт или проект.
            </p>
            <button
              type="button"
              className="btn btn-black"
              onClick={() => setIsCreateChoiceOpen(true)}
            >
              <PlusIcon />
              Новое решение
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
            <h1 className="projects-title">Мои решения</h1>
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
            Новое решение
          </button>
        </div>

        {isLoading ? (
          <div className="projects-loading">
            <Loading />
            <p>Загрузка решений...</p>
          </div>
        ) : (
          <div className={`solutions-layout ${hasRightPanel ? 'solutions-layout--with-panel' : ''}`}>
            <div className={`solutions-list ${hasRightPanel ? 'solutions-list--compact' : ''}`}>
              {solutions.map((solution) => {
                const Icon = solution.icon;
                const isSelected =
                  selectedSolution?.type === solution.type && selectedSolution?.id === solution.id;
                const isProject = solution.type === 'project';
                return (
                  <div
                    key={`${solution.type}-${solution.id}`}
                    className={`project-card solution-card ${isSelected ? 'solution-card--selected' : ''} ${
                      isProject ? 'solution-card--project' : ''
                    }`}
                    onClick={solution.onClick}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        solution.onClick();
                      }
                    }}
                  >
                    <div className="project-card-header">
                      <div className="project-card-icon">
                        <Icon />
                      </div>
                      <div className="project-card-meta">
                        <span className="project-card-date">
                          {formatDate(solution.created_at)}
                        </span>
                        <span className="project-card-badge project-card-badge--default">
                          {solution.badge}
                        </span>
                      </div>
                    </div>

                    <div className="project-card-content">
                      <h3 className="project-card-name">
                        {solution.title}
                      </h3>
                      <p className="project-card-industry">
                        {solution.subtitle}
                      </p>
                      <p className="project-card-description">
                        {solution.description}
                      </p>
                    </div>

                    {isProject && (
                      <div className="solution-card-project-action">
                        <span>Открыть проект</span>
                        <ArrowRightIcon />
                      </div>
                    )}
                  </div>
                );
              })}

              <div
                className="project-card project-card--add solution-card"
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
                  <p className="project-card-add-text">Создать новое решение</p>
                </div>
              </div>
            </div>

            {hasRightPanel && (
              <aside className="solution-details-panel">
                {isDetailsLoading ? (
                  <div className="solution-details-loading">
                    <Loading />
                    <p>Загрузка мини-дашборда...</p>
                  </div>
                ) : selectedSolution?.type === 'agent' && selectedAgent ? (
                  <div className="solution-details-content">
                    <h3 className="solution-details-title">ИИ-агент</h3>
                    <p className="solution-details-name">
                      {selectedAgent.bot_username ? `@${selectedAgent.bot_username}` : `Агент #${selectedAgent.id}`}
                    </p>
                    <div className="solution-details-list">
                      <p><strong>Тип:</strong> {selectedAgent.template_type || 'assistant'}</p>
                      <p><strong>Статус:</strong> {selectedAgent.is_active ? 'Активен' : 'Отключен'}</p>
                      <p><strong>ID:</strong> {selectedAgent.id}</p>
                    </div>
                    <button type="button" className="btn btn-black" onClick={openAgentManagement}>
                      Открыть управление агентом
                    </button>
                  </div>
                ) : selectedSolution?.type === 'website' && selectedWebsite ? (
                  <div className="solution-details-content">
                    <h3 className="solution-details-title">Сайт</h3>
                    <p className="solution-details-name">{selectedWebsite.title || `Сайт #${selectedWebsite.id}`}</p>
                    <div className="solution-details-list">
                      <p><strong>URL:</strong> /{selectedWebsite.slug || 'website'}</p>
                      <p><strong>Статус:</strong> {selectedWebsite.status || 'draft'}</p>
                      <p><strong>Генерация:</strong> {selectedWebsite.generation_status || 'idle'}</p>
                      <p><strong>Привязан к агенту:</strong> {selectedWebsite.agent_id ? `Да (#${selectedWebsite.agent_id})` : 'Нет'}</p>
                    </div>
                    <div className="solution-details-actions">
                      <button type="button" className="btn btn-black" onClick={openWebsiteEditor}>
                        Открыть конструктор
                      </button>
                      {selectedWebsite.status === 'published' && (
                        <button type="button" className="btn btn-outline" onClick={openWebsitePublic}>
                          Открыть опубликованный сайт
                        </button>
                      )}
                    </div>

                    <div className="solution-details-applications">
                      <h4>Заявки с форм сайта</h4>
                      {!selectedWebsite.agent_id ? (
                        <p className="solution-details-muted">
                          Для приёма и обработки заявок привяжите сайт к ИИ-агенту.
                        </p>
                      ) : isApplicationsLoading ? (
                        <p className="solution-details-muted">Загрузка заявок...</p>
                      ) : websiteApplications.length === 0 ? (
                        <p className="solution-details-muted">Пока нет заявок.</p>
                      ) : (
                        <div className="solution-applications-list">
                          {websiteApplications.slice(0, 10).map((item) => (
                            <div key={item.id} className="solution-application-item">
                              <p className="solution-application-title">
                                {item.client_name || `Заявка #${item.id}`}
                              </p>
                              <p className="solution-application-meta">
                                {item.status || 'new'} {item.created_at ? `• ${formatDate(item.created_at)}` : ''}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="solution-details-empty">
                    <p>Выберите агента или сайт для быстрого мини-дашборда.</p>
                  </div>
                )}
              </aside>
            )}
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
