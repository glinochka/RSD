/**
 * Projects List Page
 * Displays user's projects with cards and empty state
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../../components/Layout';
import Loading from '../../components/Loading';
import { useAuth } from '../../context/useAuth';
import { useNotification } from '../../context/useNotification';
import projectService from '../../services/projectService';
import { NAVIGATION_ROUTES } from '../../config/constants';
import '../../styles/projectsListPage.css';

// Icons
const BriefcaseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

const PlusIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const BotIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
  </svg>
);

const GlobeIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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

// Industry labels
const INDUSTRY_LABELS = {
  retail: 'Ритейл',
  beauty_salon: 'Салон красоты',
  restaurant: 'Ресторан',
  medical: 'Медицина',
  education: 'Образование',
  b2b_services: 'B2B услуги',
  logistics: 'Логистика',
  real_estate: 'Недвижимость',
  finance: 'Финансы',
  other: 'Другое',
};

const ProjectsListPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError } = useNotification();
  
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  }, [isAuthenticated, navigate]);

  // Fetch projects
  useEffect(() => {
    if (!isAuthenticated) return;

    const fetchProjects = async () => {
      try {
        setIsLoading(true);
        const response = await projectService.listProjects();
        setProjects(response.items || []);
      } catch (error) {
        console.error('Failed to load projects:', error);
        showError(error.message || 'Не удалось загрузить проекты');
      } finally {
        setIsLoading(false);
      }
    };

    fetchProjects();
  }, [isAuthenticated, showError]);

  const handleCreateProject = () => {
    navigate(NAVIGATION_ROUTES.PROJECT_CREATE);
  };

  const handleProjectClick = (projectId) => {
    navigate(NAVIGATION_ROUTES.PROJECT_DETAIL(projectId));
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  // Empty state
  if (!isLoading && projects.length === 0) {
    return (
      <MainLayout>
        <div className="projects-page">
          <div className="projects-empty-state">
            <div className="projects-empty-icon">
              <EmptyStateIcon />
            </div>
            <h2 className="projects-empty-title">У вас пока нет проектов</h2>
            <p className="projects-empty-description">
              Создайте свой первый проект и начните цифровизацию бизнеса.
              В проекте можно объединить агентов, сайт, CRM и базу знаний.
            </p>
            <button
              type="button"
              className="btn btn-black"
              onClick={handleCreateProject}
            >
              <PlusIcon />
              Создать проект
            </button>
          </div>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="projects-page">
        <div className="projects-header">
          <div className="projects-header-content">
            <h1 className="projects-title">Мои проекты</h1>
            <p className="projects-subtitle">
              Управляйте цифровизацией вашего бизнеса
            </p>
          </div>
          <button
            type="button"
            className="btn btn-black"
            onClick={handleCreateProject}
          >
            <PlusIcon />
            Новый проект
          </button>
        </div>

        {isLoading ? (
          <div className="projects-loading">
            <Loading />
            <p>Загрузка проектов...</p>
          </div>
        ) : (
          <div className="projects-grid">
            {projects.map((project) => (
              <div
                key={project.id}
                className="project-card"
                onClick={() => handleProjectClick(project.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    handleProjectClick(project.id);
                  }
                }}
              >
                <div className="project-card-header">
                  <div className="project-card-icon">
                    <BriefcaseIcon />
                  </div>
                  <div className="project-card-meta">
                    <span className="project-card-date">
                      {formatDate(project.created_at)}
                    </span>
                    {project.is_default && (
                      <span className="project-card-badge project-card-badge--default">
                        Основной
                      </span>
                    )}
                  </div>
                </div>

                <div className="project-card-content">
                  <h3 className="project-card-name">{project.name}</h3>
                  <p className="project-card-industry">
                    {INDUSTRY_LABELS[project.industry] || project.industry || 'Бизнес'}
                  </p>
                  {project.description && (
                    <p className="project-card-description">
                      {project.description.length > 100
                        ? `${project.description.substring(0, 100)}...`
                        : project.description}
                    </p>
                  )}
                </div>

                <div className="project-card-footer">
                  <div className="project-card-stats">
                    <div className="project-card-stat">
                      <BotIcon />
                      <span>{project.agents_count || 0} агентов</span>
                    </div>
                    {project.website_status && (
                      <div className="project-card-stat">
                        <GlobeIcon />
                        <span>
                          {project.website_status === 'published'
                            ? 'Сайт опубликован'
                            : project.website_status === 'draft'
                            ? 'Сайт в черновике'
                            : 'Сайт создается'}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Add new project card */}
            <div
              className="project-card project-card--add"
              onClick={handleCreateProject}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  handleCreateProject();
                }
              }}
            >
              <div className="project-card-add-content">
                <div className="project-card-add-icon">
                  <PlusIcon />
                </div>
                <p className="project-card-add-text">Создать новый проект</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </MainLayout>
  );
};

export default ProjectsListPage;
