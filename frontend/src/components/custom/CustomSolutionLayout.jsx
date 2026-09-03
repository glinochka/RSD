import React, { useEffect, useState } from 'react';
import { Link, Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useCustomAuth } from './useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';
import customService from '../../services/customService';
import '../../styles/projectLayout.css';

const DashboardIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </svg>
);

const ActivityIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
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

const ChatIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const LeadsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <line x1="19" y1="8" x2="19" y2="14" />
    <line x1="22" y1="11" x2="16" y2="11" />
  </svg>
);

const PromptIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
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

const TestIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 2v7.5L4.8 18.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9.5V2" />
    <path d="M8 2h8" />
    <path d="M8.5 14h7" />
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

const getNavItems = (automationId, features, isAdmin) => {
  const isDmpBot = features?.solution_kind === 'dmp_bot';
  return [
    { id: 'dashboard', label: 'Дашборд', icon: DashboardIcon, path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(automationId) },
    { id: 'activity', label: 'Активность', icon: ActivityIcon, path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ACTIVITY(automationId) },
    {
      id: 'accounts',
      label: 'Аккаунты',
      icon: UsersIcon,
      path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId),
      hidden: isDmpBot,
    },
    {
      id: 'chats',
      label: 'Чаты',
      icon: ChatIcon,
      path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(automationId),
      hidden: isDmpBot,
    },
    { id: 'leads', label: 'Лиды', icon: LeadsIcon, path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(automationId) },
    {
      id: 'prompts',
      label: 'Промпты',
      icon: PromptIcon,
      path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(automationId),
      hidden: isDmpBot,
    },
    {
      id: 'dmp',
      label: 'DMP.one',
      icon: PlugIcon,
      path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP(automationId),
      hidden: !features?.is_dmp_one_enabled,
    },
    {
      id: 'amocrm',
      label: 'AmoCRM',
      icon: PlugIcon,
      path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_AMOCRM(automationId),
      hidden: isDmpBot || !features?.is_amocrm_enabled,
    },
    {
      id: 'test',
      label: 'Тест',
      icon: TestIcon,
      path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_TEST(automationId),
      hidden: !isAdmin || isDmpBot,
    },
    { id: 'settings', label: 'Настройки', icon: SettingsIcon, path: NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(automationId) },
  ];
};

const CustomSolutionLayout = () => {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, isAdmin, automationId, logout } = useCustomAuth();
  const [features, setFeatures] = useState({});
  const [title, setTitle] = useState('Решение');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!id) {
      return undefined;
    }
    let mounted = true;
    customService
      .getAutomationSettings(id)
      .then((data) => {
        if (!mounted) {
          return;
        }
        setFeatures(data || {});
        setTitle(data?.name || data?.client_name || `Решение #${id}`);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [id, location.pathname]);

  if (!isAuthenticated) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }
  if (!isAdmin && String(automationId) !== String(id)) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }

  const navItems = getNavItems(id, features, isAdmin).filter((item) => !item.hidden);
  const isActive = (path) => location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <div className="project-layout">
      <header className="project-topbar">
        <div className="project-topbar-left">
          {isAdmin ? (
            <button
              type="button"
              className="project-topbar-back"
              onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN)}
            >
              <ArrowLeftIcon />
              <span>Все решения</span>
            </button>
          ) : null}
          <h1 className="project-topbar-title">{title}</h1>
        </div>
        <div className="project-topbar-right">
          <span className="project-topbar-user">{isAdmin ? 'Администратор' : 'Клиент'}</span>
          <button type="button" className="project-topbar-back" onClick={logout}>
            Выйти
          </button>
          <button
            type="button"
            className="project-topbar-menu-btn"
            onClick={() => setIsMobileMenuOpen((open) => !open)}
            aria-label="Открыть меню"
          >
            <MenuIcon />
          </button>
        </div>
      </header>

      <div className="project-layout-body">
        <aside className={`project-sidebar ${isMobileMenuOpen ? 'project-sidebar--open' : ''}`}>
          <nav className="project-sidebar-nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.id}
                  to={item.path}
                  className={`project-sidebar-item ${isActive(item.path) ? 'project-sidebar-item--active' : ''}`}
                  onClick={() => setIsMobileMenuOpen(false)}
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
        {isMobileMenuOpen ? (
          <div
            className="project-sidebar-overlay"
            onClick={() => setIsMobileMenuOpen(false)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                setIsMobileMenuOpen(false);
              }
            }}
          />
        ) : null}
        <main className="project-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default CustomSolutionLayout;
