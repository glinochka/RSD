import React, { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useCustomAuth } from './useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';
import customService from '../../services/customService';
import { UBT_MODULES, ubtModulePath } from '../../pages/custom/automation/customNav';
import '../../styles/projectLayout.css';
import '../../styles/customSolutionNav.css';

const Ico = ({ d, children }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {d ? <path d={d} /> : children}
  </svg>
);

const DashboardIcon = () => (
  <Ico>
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </Ico>
);
const UsersIcon = () => (
  <Ico>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </Ico>
);
const ListIcon = () => (
  <Ico>
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </Ico>
);
const ChartIcon = () => (
  <Ico>
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </Ico>
);
const CommentIcon = () => (
  <Ico d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
);
const ChatIcon = () => (
  <Ico>
    <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z" />
  </Ico>
);
const EyeIcon = () => (
  <Ico>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </Ico>
);
const MegaphoneIcon = () => (
  <Ico d="M3 11v2a9 9 0 0 0 9 9h1M21 5v14l-8-4H8a4 4 0 0 1 0-8h5z" />
);
const RocketIcon = () => (
  <Ico d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09zM12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
);
const FlameIcon = () => (
  <Ico d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.07-3.86-.07-3.86S6 7.24 6 11a6 6 0 0 0 9.5 4.9c.3-.2.5-.5.5-.9 0-1.38-.5-2-1-3 .07 2.14 2.07 2.86 2.07 2.86S19 12.76 19 9c0-3.76-3-7-7-7-4.5 0-8 4-8 9a8 8 0 0 0 8 8c3 0 5.5-1.5 6.5-3.5" />
);
const ContactIcon = () => (
  <Ico>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <line x1="19" y1="8" x2="19" y2="14" />
    <line x1="22" y1="11" x2="16" y2="11" />
  </Ico>
);
const SearchIcon = () => (
  <Ico>
    <circle cx="11" cy="11" r="7" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </Ico>
);
const FolderIcon = () => (
  <Ico>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </Ico>
);
const AlertIcon = () => (
  <Ico>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </Ico>
);
const KeyIcon = () => (
  <Ico>
    <path d="M21 2l-2 2m-7.6 7.6a5 5 0 1 1-2.8 2.8L3 21h3v-3h3v-3h3z" />
  </Ico>
);
const SlidersIcon = () => (
  <Ico>
    <line x1="4" y1="21" x2="4" y2="14" />
    <line x1="4" y1="10" x2="4" y2="3" />
    <line x1="12" y1="21" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12" y2="3" />
    <line x1="20" y1="21" x2="20" y2="16" />
    <line x1="20" y1="12" x2="20" y2="3" />
    <line x1="1" y1="14" x2="7" y2="14" />
    <line x1="9" y1="8" x2="15" y2="8" />
    <line x1="17" y1="16" x2="23" y2="16" />
  </Ico>
);
const SettingsIcon = () => (
  <Ico>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </Ico>
);
const PromptIcon = () => (
  <Ico>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </Ico>
);
const TestIcon = () => (
  <Ico>
    <path d="M10 2v7.5L4.8 18.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9.5V2" />
    <path d="M8 2h8" />
  </Ico>
);
const BugIcon = () => (
  <Ico>
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </Ico>
);
const PlugIcon = () => (
  <Ico>
    <path d="M12 22v-5" />
    <path d="M15 8V2" />
    <path d="M9 8V2" />
    <path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z" />
  </Ico>
);
const TelegramIcon = () => (
  <Ico>
    <path d="M22 2 11 13" />
    <path d="M22 2 15 22 11 13 2 9z" />
  </Ico>
);
const DmpIcon = () => (
  <Ico>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
    <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
  </Ico>
);
const ChevronIcon = () => (
  <svg className="ubt-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);
const ArrowLeftIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="19" y1="12" x2="5" y2="12" />
    <polyline points="12 19 5 12 12 5" />
  </svg>
);
const MenuIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

const UBT_ICONS = {
  accounts: UsersIcon,
  tasks: ListIcon,
  stats: ChartIcon,
  neurocommenting: CommentIcon,
  neurochatting: ChatIcon,
  masslooking: EyeIcon,
  'chat-broadcasts': MegaphoneIcon,
  neuroshilling: RocketIcon,
  masspriming: ContactIcon,
  warmup: FlameIcon,
  parser: SearchIcon,
};

const NavLink = ({ to, label, icon: Icon, active, nested, onClick }) => (
  <Link
    to={to}
    className={`ubt-link ${nested ? 'ubt-link--nested' : ''} ${active ? 'ubt-link--active' : ''}`}
    onClick={onClick}
  >
    {Icon ? (
      <span className="ubt-link-icon">
        <Icon />
      </span>
    ) : null}
    <span>{label}</span>
  </Link>
);

const CustomSolutionLayout = () => {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, isAdmin, automationId, logout } = useCustomAuth();
  const [features, setFeatures] = useState({});
  const [title, setTitle] = useState('Решение');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState({});

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

  const isDmpBot = features?.solution_kind === 'dmp_bot';
  const showDmp = Boolean(features?.is_dmp_one_enabled) || isDmpBot;
  const path = location.pathname;

  const activeGroup = useMemo(() => {
    if (path.includes('/ubt/')) return 'telegram';
    if (path.includes('/dmp')) return 'dmp';
    if (path.includes('/integrations') || path.includes('/amocrm')) return 'integrations';
    if (path.includes('/settings') || path.includes('/prompts') || path.includes('/test')) return 'settings';
    if (path.includes('/leads') || path.includes('/activity') || path.includes('/errors')) return 'work';
    return null;
  }, [path]);

  useEffect(() => {
    if (activeGroup) {
      setOpenGroups((prev) => ({ ...prev, [activeGroup]: true }));
    }
  }, [activeGroup]);

  if (!isAuthenticated) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }
  if (!isAdmin && String(automationId) !== String(id)) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }

  const isActive = (itemPath) => path === itemPath || path.startsWith(`${itemPath}/`);
  const closeMobile = () => setIsMobileMenuOpen(false);
  const toggleGroup = (key) => {
    setOpenGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  };
  const initials = String(title || 'RSD')
    .replace(/[^A-Za-zА-Яа-я0-9]+/g, ' ')
    .trim()
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'RSD';

  return (
    <div className="project-layout ubt-layout">
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
        <aside className={`project-sidebar ubt-sidebar ${isMobileMenuOpen ? 'project-sidebar--open' : ''}`}>
          <div className="ubt-brand">
            <span className="ubt-brand-mark">{initials}</span>
            <span className="ubt-brand-name">{title}</span>
          </div>
          <nav className="ubt-nav">
            <div className="ubt-section-label">Главная</div>
            <NavLink
              to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(id)}
              label="Общий дашборд"
              icon={DashboardIcon}
              active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(id))}
              onClick={closeMobile}
            />
            {isDmpBot ? null : (
              <NavLink
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}
                label="Чаты"
                icon={FolderIcon}
                active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id))}
                onClick={closeMobile}
              />
            )}

            {isDmpBot ? null : (
              <>
                <div className="ubt-section-label">Модули</div>
                <button
                  type="button"
                  className={`ubt-group-toggle ${openGroups.telegram ? 'ubt-group-toggle--open' : ''}`}
                  onClick={() => toggleGroup('telegram')}
                >
                  <span className="ubt-group-toggle-left">
                    <TelegramIcon />
                    Телеграм УБТ
                  </span>
                  <ChevronIcon />
                </button>
                {openGroups.telegram ? (
                  <div className="ubt-subnav">
                    {UBT_MODULES.map((item) => {
                      const Icon = UBT_ICONS[item.id] || CommentIcon;
                      const to = ubtModulePath(id, item.id);
                      return (
                        <NavLink
                          key={item.id}
                          to={to}
                          label={item.label}
                          icon={Icon}
                          nested
                          active={isActive(to)}
                          onClick={closeMobile}
                        />
                      );
                    })}
                  </div>
                ) : null}
              </>
            )}

            {showDmp ? (
              <>
                <button
                  type="button"
                  className={`ubt-group-toggle ${openGroups.dmp ? 'ubt-group-toggle--open' : ''}`}
                  onClick={() => toggleGroup('dmp')}
                >
                  <span className="ubt-group-toggle-left">
                    <DmpIcon />
                    DMP
                  </span>
                  <ChevronIcon />
                </button>
                {openGroups.dmp ? (
                  <div className="ubt-subnav">
                    <NavLink
                      to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP(id)}
                      label="Дашборд DMP"
                      icon={ChartIcon}
                      nested
                      active={path === NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP(id)}
                      onClick={closeMobile}
                    />
                    <NavLink
                      to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_CONNECTION(id)}
                      label="Подключение"
                      icon={KeyIcon}
                      nested
                      active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_CONNECTION(id))}
                      onClick={closeMobile}
                    />
                    <NavLink
                      to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_SETTINGS(id)}
                      label="Настройки"
                      icon={SlidersIcon}
                      nested
                      active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_SETTINGS(id))}
                      onClick={closeMobile}
                    />
                  </div>
                ) : null}
              </>
            ) : null}

            <button
              type="button"
              className={`ubt-group-toggle ${openGroups.work ? 'ubt-group-toggle--open' : ''}`}
              onClick={() => toggleGroup('work')}
            >
              <span className="ubt-group-toggle-left">
                <UsersIcon />
                Лиды и лента
              </span>
              <ChevronIcon />
            </button>
            {openGroups.work ? (
              <div className="ubt-subnav">
                <NavLink
                  to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id)}
                  label="Лиды"
                  icon={UsersIcon}
                  nested
                  active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id))}
                  onClick={closeMobile}
                />
                <NavLink
                  to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ACTIVITY(id)}
                  label="Активность"
                  icon={BugIcon}
                  nested
                  active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ACTIVITY(id))}
                  onClick={closeMobile}
                />
                {isAdmin ? (
                  <NavLink
                    to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ERRORS(id)}
                    label="Баги и ошибки"
                    icon={AlertIcon}
                    nested
                    active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ERRORS(id))}
                    onClick={closeMobile}
                  />
                ) : null}
              </div>
            ) : null}

            <button
              type="button"
              className={`ubt-group-toggle ${openGroups.settings ? 'ubt-group-toggle--open' : ''}`}
              onClick={() => toggleGroup('settings')}
            >
              <span className="ubt-group-toggle-left">
                <SettingsIcon />
                Общие настройки
              </span>
              <ChevronIcon />
            </button>
            {openGroups.settings ? (
              <div className="ubt-subnav">
                <NavLink
                  to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id)}
                  label="Настройки"
                  icon={SlidersIcon}
                  nested
                  active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id))}
                  onClick={closeMobile}
                />
                {isDmpBot ? null : (
                  <NavLink
                    to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)}
                    label="Промпты"
                    icon={PromptIcon}
                    nested
                    active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id))}
                    onClick={closeMobile}
                  />
                )}
                {isAdmin && !isDmpBot ? (
                  <NavLink
                    to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_TEST(id)}
                    label="Тест"
                    icon={TestIcon}
                    nested
                    active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_TEST(id))}
                    onClick={closeMobile}
                  />
                ) : null}
              </div>
            ) : null}

            <NavLink
              to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_INTEGRATIONS(id)}
              label="Интеграции"
              icon={PlugIcon}
              active={isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_INTEGRATIONS(id)) || isActive(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_AMOCRM(id))}
              onClick={closeMobile}
            />
          </nav>
        </aside>
        {isMobileMenuOpen ? (
          <div
            className="project-sidebar-overlay"
            onClick={closeMobile}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                closeMobile();
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
