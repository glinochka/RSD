/**
 * ProjectLayout Component
 * Layout wrapper for project pages with sidebar navigation
 */

import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import { useNotification } from '../../context/useNotification';
import projectService from '../../services/projectService';
import { NAVIGATION_ROUTES } from '../../config/constants';
import ProjectErrorBoundary from './ProjectErrorBoundary';
import '../../styles/projectLayout.css';

// Icons
const DashboardIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </svg>
);

const BotIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
  </svg>
);

const BookOpenIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const UsersIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const GlobeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const VideoIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="23 7 16 12 23 17 23 7" />
    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
  </svg>
);

const PhoneIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const ArrowLeftIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="19" y1="12" x2="5" y2="12" />
    <polyline points="12 19 5 12 12 5" />
  </svg>
);

const MenuIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

const PlugIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22v-5" />
    <path d="M15 8V2" />
    <path d="M9 8V2" />
    <path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z" />
  </svg>
);

// Navigation items
const getNavItems = (projectId) => [
  { id: 'dashboard', label: 'Дашборд', icon: DashboardIcon, path: NAVIGATION_ROUTES.PROJECT_DETAIL(projectId) },
  { id: 'agents', label: 'Агенты', icon: BotIcon, path: NAVIGATION_ROUTES.PROJECT_AGENTS(projectId) },
  { id: 'knowledge', label: 'База знаний', icon: BookOpenIcon, path: NAVIGATION_ROUTES.PROJECT_KNOWLEDGE(projectId) },
  { id: 'crm', label: 'CRM', icon: UsersIcon, path: NAVIGATION_ROUTES.PROJECT_CRM(projectId) },
  { id: 'website', label: 'Сайты', icon: GlobeIcon, path: NAVIGATION_ROUTES.PROJECT_WEBSITE(projectId) },
  { id: 'content', label: 'Контент', icon: VideoIcon, path: NAVIGATION_ROUTES.PROJECT_CONTENT(projectId), hidden: true },
  { id: 'manager', label: 'ИИ-менеджер', icon: PhoneIcon, path: NAVIGATION_ROUTES.PROJECT_MANAGER(projectId) },
  { id: 'settings', label: 'Настройки', icon: SettingsIcon, path: NAVIGATION_ROUTES.PROJECT_SETTINGS(projectId) },
  { id: 'integrations', label: 'Интеграции', icon: PlugIcon, path: NAVIGATION_ROUTES.PROJECT_INTEGRATIONS(projectId) },
];

const ProjectLayout = ({ children }) => {
  const { projectId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const { showError } = useNotification();

  const [project, setProject] = useState(null);
  const [agents, setAgents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Check which agent types are present
  const hasContentFactory = agents.some(a => a.template_type === 'content_factory');

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH, { state: { from: location.pathname } });
    }
  }, [isAuthenticated, navigate, location.pathname]);

  // Fetch project and agents
  useEffect(() => {
    if (!isAuthenticated || !projectId) {
      return;
    }

    const fetchProject = async () => {
      try {
        setIsLoading(true);
        const [projectData, agentsData] = await Promise.all([
          projectService.getProject(projectId),
          projectService.getProjectAgents(projectId).catch(() => []),
        ]);

        // Edge case: archived project should show 404
        if (projectData.status === 'archived') {
          showError('Проект архивирован и недоступен');
          navigate(NAVIGATION_ROUTES.PROJECTS_LIST, { replace: true });
          return;
        }

        setProject(projectData);
        setAgents(agentsData);
        // Store last visited project
        localStorage.setItem('rsd_last_project_id', projectId);
      } catch (error) {
        console.error('Failed to load project:', error);
        const errorMessage = error.message || 'Не удалось загрузить проект';
        showError(errorMessage);
        // Redirect to projects list after a short delay to allow error notification
        setTimeout(() => {
          navigate(NAVIGATION_ROUTES.PROJECTS_LIST, { replace: true });
        }, 1500);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProject();
  }, [isAuthenticated, projectId, navigate, showError]);

  // Dynamic nav items based on agent presence
  const navItems = getNavItems(projectId).filter(item => {
    if (item.id === 'content' && !hasContentFactory) {
      return false;
    }
    return !item.hidden;
  });

  const isActive = (path) => location.pathname === path;

  const handleBackToProjects = () => {
    navigate(NAVIGATION_ROUTES.PROJECTS_LIST);
  };

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="project-layout project-layout--loading">
        <div className="project-layout-loading">
          <div className="spinner" />
          <p>Загрузка проекта...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-layout">
      {/* Top bar */}
      <header className="project-topbar">
        <div className="project-topbar-left">
          <button
            type="button"
            className="project-topbar-back"
            onClick={handleBackToProjects}
          >
            <ArrowLeftIcon />
            <span>Проекты</span>
          </button>
          <h1 className="project-topbar-title">
            {project?.name || 'Проект'}
          </h1>
        </div>

        <div className="project-topbar-right">
          <span className="project-topbar-user">
            {user?.name || user?.email || 'Пользователь'}
          </span>
          <button
            type="button"
            className="project-topbar-menu-btn"
            onClick={toggleMobileMenu}
            aria-label="Открыть меню"
          >
            <MenuIcon />
          </button>
        </div>
      </header>

      <div className="project-layout-body">
        {/* Sidebar */}
        <aside className={`project-sidebar ${isMobileMenuOpen ? 'project-sidebar--open' : ''}`}>
          <nav className="project-sidebar-nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.path);

              return (
                <Link
                  key={item.id}
                  to={item.path}
                  className={`project-sidebar-item ${active ? 'project-sidebar-item--active' : ''}`}
                  onClick={closeMobileMenu}
                  title={item.label}
                >
                  <span className="project-sidebar-icon">
                    <Icon />
                  </span>
                  <span className="project-sidebar-label">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Mobile overlay */}
        {isMobileMenuOpen && (
          <div
            className="project-sidebar-overlay"
            onClick={closeMobileMenu}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                closeMobileMenu();
              }
            }}
          />
        )}

        {/* Main content with Error Boundary */}
        <main className="project-content">
          <ProjectErrorBoundary>
            {children}
          </ProjectErrorBoundary>
        </main>
      </div>
    </div>
  );
};

export default ProjectLayout;
