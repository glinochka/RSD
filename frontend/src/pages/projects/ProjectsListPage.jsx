/**
 * Solutions List Page
 * Horizontal rows list + right-side mini-dashboard for agents and websites
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
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const EmptyStateIcon = () => (
  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />
  </svg>
);

const TEMPLATE_LABELS = {
  qa: 'Поддержка',
  assistant: 'Ассистент',
  sales_manager: 'Продажи',
  crm_admin: 'Администратор',
  content_factory: 'Контент',
};

const formatDate = (dateString) => {
  if (!dateString) {
    return '';
  }
  return new Date(dateString).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

const ProjectsListPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError } = useNotification();

  const [projects, setProjects] = useState([]);
  const [agents, setAgents] = useState([]);
  const [websites, setWebsites] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateChoiceOpen, setIsCreateChoiceOpen] = useState(false);

  const [selectedKey, setSelectedKey] = useState(null); // "agent-123" | "website-456"
  const [panelAgent, setPanelAgent] = useState(null);
  const [panelWebsite, setPanelWebsite] = useState(null);
  const [isPanelLoading, setIsPanelLoading] = useState(false);
  const [webLeads, setWebLeads] = useState([]);
  const [isLeadsLoading, setIsLeadsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }
    const load = async () => {
      try {
        setIsLoading(true);
        const [pRes, aRes, wRes] = await Promise.all([
          projectService.listProjects(),
          agentService.getAll(),
          websiteService.list({ page: 1, page_size: 100 }),
        ]);
        setProjects(Array.isArray(pRes?.items) ? pRes.items : []);
        setAgents(Array.isArray(aRes) ? aRes : []);
        setWebsites(Array.isArray(wRes?.items) ? wRes.items : []);
      } catch (err) {
        showError(err?.message || 'Не удалось загрузить решения');
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [isAuthenticated, showError]);

  // Load panel details when selection changes
  useEffect(() => {
    if (!selectedKey) {
      setPanelAgent(null);
      setPanelWebsite(null);
      setWebLeads([]);
      return;
    }

    const [type, idStr] = selectedKey.split('-');
    const id = Number(idStr);
    let cancelled = false;

    const loadPanel = async () => {
      setIsPanelLoading(true);
      setPanelAgent(null);
      setPanelWebsite(null);
      setWebLeads([]);
      try {
        if (type === 'agent') {
          const detail = await agentService.getById(id);
          if (!cancelled) {
            setPanelAgent(detail || null);
          }
        } else if (type === 'website') {
          const detail = await websiteService.getById(id);
          if (!cancelled) {
            setPanelWebsite(detail || null);
          }
        }
      } catch (err) {
        if (!cancelled) {
          showError(err?.message || 'Не удалось загрузить детали');
        }
      } finally {
        if (!cancelled) {
          setIsPanelLoading(false);
        }
      }
    };

    loadPanel();
    return () => {
      cancelled = true;
    };
  }, [selectedKey, showError]);

  // Load website form leads when website panel with agent_id is shown
  useEffect(() => {
    if (!panelWebsite?.agent_id) {
      setWebLeads([]);
      return;
    }
    let cancelled = false;
    const loadLeads = async () => {
      setIsLeadsLoading(true);
      try {
        const res = await agentService.listAdminTemplateApplications({
          agent_id: panelWebsite.agent_id,
          source_channel: 'website',
          limit: 20,
          offset: 0,
        });
        if (!cancelled) {
          setWebLeads(Array.isArray(res?.items) ? res.items : []);
        }
      } catch {
        // Leads unavailable for this agent type — silently show empty
        if (!cancelled) {
          setWebLeads([]);
        }
      } finally {
        if (!cancelled) {
          setIsLeadsLoading(false);
        }
      }
    };
    loadLeads();
    return () => {
      cancelled = true;
    };
  }, [panelWebsite?.agent_id]);

  const selectRow = (key) => {
    setSelectedKey((prev) => (prev === key ? null : key));
  };

  const hasPanel = selectedKey !== null;

  const allRows = [
    ...projects.map((p) => ({ key: `project-${p.id}`, type: 'project', id: p.id, created_at: p.created_at, title: p.name || `Проект #${p.id}`, sub: p.industry || 'Проект', status: p.description ? p.description.slice(0, 60) : null })),
    ...agents.map((a) => ({ key: `agent-${a.id}`, type: 'agent', id: a.id, created_at: a.created_at, title: a.bot_username ? `@${a.bot_username}` : `Агент #${a.id}`, sub: TEMPLATE_LABELS[a.template_type] || a.template_type || 'Агент', status: a.is_active ? 'active' : 'inactive' })),
    ...websites.map((w) => ({ key: `website-${w.id}`, type: 'website', id: w.id, created_at: w.created_at, title: w.title || `Сайт #${w.id}`, sub: `/${w.slug || ''}`, status: w.status === 'published' ? 'published' : w.generation_status === 'generating' || w.generation_status === 'queued' ? 'generating' : 'draft' })),
  ].sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());

  if (!isLoading && allRows.length === 0) {
    return (
      <MainLayout>
        <div className="projects-page">
          <div className="projects-empty-state">
            <div className="projects-empty-icon"><EmptyStateIcon /></div>
            <h2 className="projects-empty-title">У вас пока нет решений</h2>
            <p className="projects-empty-description">Создайте первое решение: отдельный ИИ-агент, сайт или проект.</p>
            <button type="button" className="btn btn-black" onClick={() => setIsCreateChoiceOpen(true)}>
              <PlusIcon />
              Новое решение
            </button>
          </div>
          <CreateChoiceModal isOpen={isCreateChoiceOpen} onClose={() => setIsCreateChoiceOpen(false)} />
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
            <p className="projects-subtitle">ИИ-агенты, сайты и проекты</p>
          </div>
          <button type="button" className="btn btn-black" onClick={() => setIsCreateChoiceOpen(true)}>
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
          <div className={`sl-layout${hasPanel ? ' sl-layout--panel' : ''}`}>
            {/* Left: solution rows */}
            <div className="sl-list">
              {allRows.map((row) => {
                const isSelected = selectedKey === row.key;
                const isProject = row.type === 'project';
                return (
                  <div
                    key={row.key}
                    className={`sl-row sl-row--${row.type}${isSelected ? ' sl-row--selected' : ''}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      if (isProject) {
                        navigate(NAVIGATION_ROUTES.PROJECT_DETAIL(row.id));
                      } else {
                        selectRow(row.key);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        if (isProject) {
                          navigate(NAVIGATION_ROUTES.PROJECT_DETAIL(row.id));
                        } else {
                          selectRow(row.key);
                        }
                      }
                    }}
                  >
                    <span className="sl-row__dot" />
                    <div className="sl-row__body">
                      <span className="sl-row__title">{row.title}</span>
                      <span className="sl-row__sub">{row.sub}</span>
                    </div>
                    <div className="sl-row__right">
                      {row.type === 'agent' && (
                        <span className={`sl-status sl-status--${row.status}`}>
                          {row.status === 'active' ? 'Активен' : 'Отключён'}
                        </span>
                      )}
                      {row.type === 'website' && (
                        <span className={`sl-status sl-status--${row.status}`}>
                          {row.status === 'published' ? 'Опубликован' : row.status === 'generating' ? 'Генерируется' : 'Черновик'}
                        </span>
                      )}
                      <span className="sl-row__date">{formatDate(row.created_at)}</span>
                      <ChevronRightIcon />
                    </div>
                  </div>
                );
              })}

              {/* Add row */}
              <div
                className="sl-row sl-row--add"
                role="button"
                tabIndex={0}
                onClick={() => setIsCreateChoiceOpen(true)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    setIsCreateChoiceOpen(true);
                  }
                }}
              >
                <span className="sl-row__dot sl-row__dot--add" />
                <span className="sl-row__add-label">Создать новое решение</span>
              </div>
            </div>

            {/* Right: mini-dashboard */}
            {hasPanel && (
              <aside className="sl-panel">
                {isPanelLoading ? (
                  <div className="sl-panel__loading">
                    <Loading />
                  </div>
                ) : panelAgent ? (
                  <AgentPanel
                    agent={panelAgent}
                    onManage={() => navigate(NAVIGATION_ROUTES.AGENTS)}
                    onAnalytics={() => navigate(NAVIGATION_ROUTES.AGENT_ANALYTICS(panelAgent.id))}
                    onEdit={() => navigate(`${NAVIGATION_ROUTES.CREATE_AGENT}/${panelAgent.id}`)}
                  />
                ) : panelWebsite ? (
                  <WebsitePanel
                    website={panelWebsite}
                    leads={webLeads}
                    isLeadsLoading={isLeadsLoading}
                    onEditor={() => navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(panelWebsite.id))}
                    onPublic={() => window.open(NAVIGATION_ROUTES.WEBSITE_PUBLIC(panelWebsite.slug), '_blank', 'noopener,noreferrer')}
                  />
                ) : null}
              </aside>
            )}
          </div>
        )}
      </div>

      <CreateChoiceModal isOpen={isCreateChoiceOpen} onClose={() => setIsCreateChoiceOpen(false)} />
    </MainLayout>
  );
};

/* ── Agent mini-dashboard ── */
const AgentPanel = ({ agent, onManage, onAnalytics, onEdit }) => {
  const channels = Array.isArray(agent.channels) ? agent.channels : [];
  const activeChannels = channels.filter((c) => c.is_active);

  return (
    <div className="sl-panel__content">
      <div className="sl-panel__header">
        <div>
          <p className="sl-panel__label">ИИ-агент</p>
          <h3 className="sl-panel__name">
            {agent.bot_username ? `@${agent.bot_username}` : `Агент #${agent.id}`}
          </h3>
        </div>
        <span className={`sl-status sl-status--${agent.is_active ? 'active' : 'inactive'}`}>
          {agent.is_active ? 'Активен' : 'Отключён'}
        </span>
      </div>

      <div className="sl-panel__meta">
        <span className="sl-panel__tag">{TEMPLATE_LABELS[agent.template_type] || agent.template_type || 'assistant'}</span>
        <span className="sl-panel__tag sl-panel__tag--id">ID {agent.id}</span>
      </div>

      {agent.system_prompt ? (
        <div className="sl-panel__prompt">
          <p className="sl-panel__prompt-label">Системный промпт</p>
          <p className="sl-panel__prompt-text">
            {agent.system_prompt.length > 240
              ? `${agent.system_prompt.slice(0, 240)}…`
              : agent.system_prompt}
          </p>
        </div>
      ) : null}

      {activeChannels.length > 0 && (
        <div className="sl-panel__channels">
          <p className="sl-panel__channels-label">Каналы ({activeChannels.length})</p>
          <div className="sl-panel__channels-list">
            {activeChannels.map((ch) => (
              <span key={ch.id || ch.provider} className="sl-channel-tag">
                {ch.provider === 'telegram_bot' ? 'Telegram Бот' : ch.provider === 'telegram_userbot' ? 'Telegram Userbot' : ch.provider === 'max_bot' ? 'MAX Bot' : ch.provider === 'whatsapp_userbot' ? 'WhatsApp' : ch.provider === 'telephony' ? 'Телефония' : ch.provider}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="sl-panel__actions">
        <button type="button" className="btn btn-black" onClick={onManage}>
          Управление
        </button>
        <button type="button" className="btn btn-outline" onClick={onEdit}>
          Настроить
        </button>
        <button type="button" className="btn btn-outline" onClick={onAnalytics}>
          Аналитика
        </button>
      </div>
    </div>
  );
};

/* ── Website mini-dashboard ── */
const WebsitePanel = ({ website, leads, isLeadsLoading, onEditor, onPublic }) => {
  const statusLabel = website.status === 'published' ? 'Опубликован' : website.generation_status === 'queued' || website.generation_status === 'generating' ? 'Генерируется' : 'Черновик';
  const statusKey = website.status === 'published' ? 'published' : website.generation_status === 'queued' || website.generation_status === 'generating' ? 'generating' : 'draft';

  return (
    <div className="sl-panel__content">
      <div className="sl-panel__header">
        <div>
          <p className="sl-panel__label">Сайт</p>
          <h3 className="sl-panel__name">{website.title || `Сайт #${website.id}`}</h3>
        </div>
        <span className={`sl-status sl-status--${statusKey}`}>{statusLabel}</span>
      </div>

      <div className="sl-panel__meta">
        <span className="sl-panel__tag">/{website.slug || 'website'}</span>
        {website.agent_id && <span className="sl-panel__tag">Агент #{website.agent_id}</span>}
      </div>

      <div className="sl-panel__actions">
        <button type="button" className="btn btn-black" onClick={onEditor}>
          Конструктор
        </button>
        {website.status === 'published' && (
          <button type="button" className="btn btn-outline" onClick={onPublic}>
            Открыть сайт
          </button>
        )}
      </div>

      <div className="sl-panel__leads">
        <p className="sl-panel__leads-title">Заявки с форм</p>
        {!website.agent_id ? (
          <p className="sl-panel__leads-empty">Привяжите агента, чтобы принимать заявки.</p>
        ) : isLeadsLoading ? (
          <p className="sl-panel__leads-empty">Загрузка…</p>
        ) : leads.length === 0 ? (
          <p className="sl-panel__leads-empty">Заявок пока нет.</p>
        ) : (
          <div className="sl-leads-list">
            {leads.slice(0, 10).map((item) => (
              <div key={item.id} className="sl-lead-item">
                <span className="sl-lead-item__name">{item.client_name || `Заявка #${item.id}`}</span>
                <span className={`sl-status sl-status--lead-${item.status || 'new'}`}>{item.status || 'new'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectsListPage;
