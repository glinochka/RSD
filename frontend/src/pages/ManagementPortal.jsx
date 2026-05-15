import React, { useEffect, useMemo, useRef, useState } from 'react';
import adminService from '../services/adminService';
import salesService from '../services/salesService';
import { ENV_CONFIG } from '../config/environment';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/managementPortal.css';

const ADMIN_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.ADMIN_TOKEN;
const SALES_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.SALES_TOKEN;

const SALES_ROLE_LABELS = { trainee: 'Стажер', mop: 'МОП', rop: 'РОП' };
const FUNNEL_LABELS = {
  in_base: 'В базе',
  called: 'В работе',
  demo: 'Демо',
  closed: 'Закрыто',
  rejected: 'Отказ',
  hesitating: 'Сомневается',
};

const WORKFLOW_STATUS_LABELS = {
  new: 'Новый',
  in_progress: 'Взят в работу',
  demo: 'Демо',
  closed: 'Закрыт',
  rejected: 'Отказ',
  hesitating: 'Сомневается',
};

function SalesMemberPlanRow({
  member,
  onSave,
  busy,
  showSupervisor = true,
}) {
  const [calls, setCalls] = useState(member.plan_calls_monthly ?? 0);
  const [demos, setDemos] = useState(member.plan_demos_monthly ?? 0);
  const [closes, setCloses] = useState(member.plan_closes_monthly ?? 0);
  const [daily, setDaily] = useState(member.daily_contacts_quota ?? 0);

  useEffect(() => {
    setCalls(member.plan_calls_monthly ?? 0);
    setDemos(member.plan_demos_monthly ?? 0);
    setCloses(member.plan_closes_monthly ?? 0);
    setDaily(member.daily_contacts_quota ?? 0);
  }, [member]);

  return (
    <tr>
      <td>{member.id}</td>
      <td>{member.login}</td>
      <td>{SALES_ROLE_LABELS[member.role] || member.role}</td>
      {showSupervisor && <td>{member.supervisor_id ?? '—'}</td>}
      <td>
        <input
          className="management-inline-num"
          type="number"
          min={0}
          value={calls}
          onChange={(e) => setCalls(Number(e.target.value))}
        />
      </td>
      <td>
        <input
          className="management-inline-num"
          type="number"
          min={0}
          value={demos}
          onChange={(e) => setDemos(Number(e.target.value))}
        />
      </td>
      <td>
        <input
          className="management-inline-num"
          type="number"
          min={0}
          value={closes}
          onChange={(e) => setCloses(Number(e.target.value))}
        />
      </td>
      <td>
        <input
          className="management-inline-num"
          type="number"
          min={0}
          value={daily}
          onChange={(e) => setDaily(Number(e.target.value))}
        />
      </td>
      <td>
        <button
          type="button"
          className="btn btn-sm btn-black"
          disabled={!!busy}
          onClick={() =>
            onSave(member.id, {
              plan_calls_monthly: calls,
              plan_demos_monthly: demos,
              plan_closes_monthly: closes,
              daily_contacts_quota: daily,
            })
          }
        >
          {busy ? '…' : 'Сохранить'}
        </button>
      </td>
    </tr>
  );
}

function splitContactTokens(raw) {
  if (raw == null || String(raw).trim() === '') return [];
  return String(raw)
    .split(/[,;|/\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function SalesContactTokens({ value }) {
  const parts = splitContactTokens(value);
  if (!parts.length) return <span>—</span>;
  const wrap = parts.length > 2;
  return (
    <div
      className={`management-contact-values${wrap ? ' management-contact-values-wrap' : ''}`}
    >
      {parts.map((p, i) => (
        <span key={i} className="management-contact-value-chip">
          {p}
        </span>
      ))}
    </div>
  );
}

function SalesContactRow({ contact, busy, onSaveRow, onInvoice, readOnly = false }) {
  const [lprName, setLprName] = useState(contact.lpr_name || '');
  const [lprPhone, setLprPhone] = useState(contact.lpr_phone || '');
  const [comment, setComment] = useState(contact.comment || '');
  const [status, setStatus] = useState(contact.workflow_status || 'new');

  useEffect(() => {
    setLprName(contact.lpr_name || '');
    setLprPhone(contact.lpr_phone || '');
    setComment(contact.comment || '');
    setStatus(contact.workflow_status || 'new');
  }, [
    contact.id,
    contact.lpr_name,
    contact.lpr_phone,
    contact.comment,
    contact.workflow_status,
    contact.updated_at,
  ]);

  const save = () => {
    onSaveRow(contact.id, {
      lpr_name: lprName,
      lpr_phone: lprPhone,
      comment,
      workflow_status: status,
    });
  };

  const site = contact.website || '';
  const siteHref = site && !/^https?:\/\//i.test(site) ? `https://${site}` : site;

  return (
    <tr>
      <td>{contact.id}</td>
      <td>{contact.org_name || '—'}</td>
      <td>
        {readOnly ? (
          <span title={lprName || ''}>{lprName || '—'}</span>
        ) : (
          <input
            type="text"
            className="management-table-input contact-lpr-field"
            value={lprName}
            onChange={(e) => setLprName(e.target.value)}
            placeholder="ФИО ЛПР"
          />
        )}
      </td>
      <td>
        {readOnly ? (
          <span title={lprPhone || ''}>{lprPhone || '—'}</span>
        ) : (
          <input
            type="text"
            className="management-table-input contact-lpr-field"
            value={lprPhone}
            onChange={(e) => setLprPhone(e.target.value)}
            placeholder="Телефон ЛПР"
          />
        )}
      </td>
      <td>
        <SalesContactTokens value={contact.org_phone} />
      </td>
      <td>
        <SalesContactTokens value={contact.org_mobile} />
      </td>
      <td>
        {readOnly ? (
          WORKFLOW_STATUS_LABELS[status] || status
        ) : (
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="management-table-input"
          >
            {Object.entries(WORKFLOW_STATUS_LABELS).map(([k, lab]) => (
              <option key={k} value={k}>{lab}</option>
            ))}
          </select>
        )}
      </td>
      <td>
        {readOnly ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{comment || '—'}</span>
        ) : (
          <textarea
            className="management-table-textarea"
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Комментарий"
          />
        )}
      </td>
      <td>
        <SalesContactTokens value={contact.email} />
      </td>
      <td>
        {site ? (
          <a
            href={siteHref}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm btn-outline"
          >
            Перейти
          </a>
        ) : (
          <span>—</span>
        )}
      </td>
      <td>
        {!readOnly ? (
          <div className="management-sales-contact-actions">
            <button type="button" className="btn btn-sm btn-black" disabled={!!busy} onClick={save}>
              Сохранить
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline"
              disabled={!!busy}
              onClick={() => onInvoice(contact)}
            >
              Чек
            </button>
          </div>
        ) : (
          <span className="management-cell-muted">—</span>
        )}
      </td>
    </tr>
  );
}

const MENU_ITEMS = [
  { id: 'overview', label: 'Обзор' },
  { id: 'users', label: 'Пользователи' },
  { id: 'agents', label: 'Агенты' },
  { id: 'chats', label: 'Чаты' },
  { id: 'turnkeyRequests', label: 'Заявки под ключ' },
  { id: 'errorReports', label: 'Сообщения об ошибках' },
  { id: 'billing', label: 'Тарифы' },
  { id: 'promoCodes', label: 'Промокоды' },
  { id: 'emailBroadcast', label: 'Email рассылка' },
  { id: 'contentPublisher', label: '📝 Контент' },
  { id: 'salesDepartment', label: 'Отдел продаж' },
];

function formatError(error) {
  return (
    error?.response?.data?.detail
    || error?.message
    || 'Не удалось выполнить запрос к админ-панели'
  );
}

function formatChatChannel(channel) {
  const map = {
    telegram: 'Telegram Bot',
    telegram_userbot: 'Telegram Userbot',
    whatsapp_userbot: 'WhatsApp',
    external_api: 'External API',
    max_bot: 'MAX Bot',
    max_userbot: 'MAX Userbot',
    dashboard: 'Оператор',
  };
  return map[channel] || channel || '—';
}

const ManagementPortal = () => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [adminToken, setAdminToken] = useState(localStorage.getItem(ADMIN_TOKEN_KEY) || '');
  const [salesToken, setSalesToken] = useState(localStorage.getItem(SALES_TOKEN_KEY) || '');
  const [loginPortal, setLoginPortal] = useState('admin');
  const [salesSection, setSalesSection] = useState('desk');
  const [salesMe, setSalesMe] = useState(null);
  const [salesContacts, setSalesContacts] = useState({
    items: [],
    page: 1,
    totalPages: 1,
    total: 0,
  });
  const [salesContactsScope, setSalesContactsScope] = useState('active');
  const [salesDeskLoading, setSalesDeskLoading] = useState(false);
  const [salesDeskError, setSalesDeskError] = useState('');

  const [salesDeptMembers, setSalesDeptMembers] = useState([]);
  const [salesDeptFunnel, setSalesDeptFunnel] = useState(null);
  const [salesDeptLoading, setSalesDeptLoading] = useState(false);
  const [salesNewMember, setSalesNewMember] = useState({
    login: '',
    password: '',
    role: 'trainee',
    supervisor_id: '',
  });
  const [salesManualContact, setSalesManualContact] = useState({ org_name: '', label: '' });
  const [salesTeamBusy, setSalesTeamBusy] = useState(null);
  const [salesInvoiceModal, setSalesInvoiceModal] = useState({
    open: false,
    contact: null,
    amountRub: '10000',
    serviceName: '',
    clientInn: '',
  });
  const [stats, setStats] = useState(null);
  const [activeSection, setActiveSection] = useState('overview');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  const [isLoadingTable, setIsLoadingTable] = useState(false);
  const [usersState, setUsersState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [agentsState, setAgentsState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [requestsState, setRequestsState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [errorReportsState, setErrorReportsState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [chatsState, setChatsState] = useState({
    items: [],
    page: 1,
    pageSize: 25,
    totalPages: 1,
    total: 0,
    search: '',
    agentId: '',
    agentUsername: '',
  });
  const [selectedChatKey, setSelectedChatKey] = useState(null);

  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [isSavingPlans, setIsSavingPlans] = useState(false);
  const [plansDraft, setPlansDraft] = useState([]);
  const [isLoadingPromoCodes, setIsLoadingPromoCodes] = useState(false);
  const [promoCodes, setPromoCodes] = useState([]);
  const [promoCodeDraft, setPromoCodeDraft] = useState({ code: '', discountPercent: 0 });
  const [actionInProgress, setActionInProgress] = useState(null);
  const [giftModal, setGiftModal] = useState({ open: false, user: null, planCode: 'Advanced' });
  const [broadcastDraft, setBroadcastDraft] = useState({ subject: '', body: '' });
  const [broadcastIntervalSeconds, setBroadcastIntervalSeconds] = useState(900);
  const [broadcastJobId, setBroadcastJobId] = useState(null);
  const [broadcastJobStatus, setBroadcastJobStatus] = useState(null);

  const targetedGroupIdRef = useRef(2);
  const [targetedGroups, setTargetedGroups] = useState([
    { id: 'g1', title: 'Группа 1', emailsRaw: '', selected: true },
  ]);
  const [targetedBroadcastDraft, setTargetedBroadcastDraft] = useState({ subject: '', body: '' });
  const [targetedIntervalSeconds, setTargetedIntervalSeconds] = useState(900);
  const [targetedPreview, setTargetedPreview] = useState(null);
  const [targetedJobStatus, setTargetedJobStatus] = useState(null);
  const [targetedJobId, setTargetedJobId] = useState(null);
  const [targetedPreviewLoading, setTargetedPreviewLoading] = useState(false);

  // --- Content Publisher state ---
  const [apTab, setApTab] = useState('settings');
  const [apSettings, setApSettings] = useState(null);
  const [apSettingsDraft, setApSettingsDraft] = useState({});
  const [apIsLoadingSettings, setApIsLoadingSettings] = useState(false);
  const [apIsSavingSettings, setApIsSavingSettings] = useState(false);
  const [apTopics, setApTopics] = useState([]);
  const [apTopicsTotal, setApTopicsTotal] = useState(0);
  const [apIsLoadingTopics, setApIsLoadingTopics] = useState(false);
  const [apNewTopicsText, setApNewTopicsText] = useState('');
  const [apImages, setApImages] = useState([]);
  const [apIsLoadingImages, setApIsLoadingImages] = useState(false);
  const [apJobs, setApJobs] = useState([]);
  const [apJobsTotal, setApJobsTotal] = useState(0);
  const [apIsLoadingJobs, setApIsLoadingJobs] = useState(false);
  const [apRunNowPlatform, setApRunNowPlatform] = useState('');
  const [apRunNowTopic, setApRunNowTopic] = useState('');
  const [apPreviewTopic, setApPreviewTopic] = useState('');
  const [apPreviewResult, setApPreviewResult] = useState(null);
  const [apActionInProgress, setApActionInProgress] = useState(null);
  const [apError, setApError] = useState('');
  const [apSuccess, setApSuccess] = useState('');

  const statsCards = useMemo(() => {
    if (!stats) return [];
    return [
      { key: 'users_total', title: 'Пользователи', value: stats.users_total ?? 0 },
      { key: 'agents_total', title: 'Агенты', value: stats.agents_total ?? 0 },
      { key: 'agents_active', title: 'Активные агенты', value: stats.agents_active ?? 0 },
      { key: 'documents_total', title: 'Документы', value: stats.documents_total ?? 0 },
      { key: 'paid_users_total', title: 'Платные пользователи', value: stats.paid_users_total ?? 0 },
      { key: 'payments_total', title: 'Платежи', value: stats.payments_total ?? 0 },
    ];
  }, [stats]);

  const planCards = useMemo(() => {
    const byPlan = stats?.users_by_plan ?? {};
    return [
      { key: 'free', title: 'Free', value: byPlan.Free ?? 0 },
      { key: 'advanced', title: 'Advanced', value: byPlan.Advanced ?? 0 },
      { key: 'pro', title: 'Pro', value: byPlan.Pro ?? 0 },
    ];
  }, [stats]);

  useEffect(() => {
    const fetchStats = async () => {
      if (!adminToken) {
        setStats(null);
        return;
      }
      try {
        setIsLoadingStats(true);
        setError('');
        const data = await adminService.getStats(adminToken);
        setStats(data);
      } catch (err) {
        setError(formatError(err));
        setStats(null);
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        setAdminToken('');
      } finally {
        setIsLoadingStats(false);
      }
    };

    fetchStats();
  }, [adminToken]);

  useEffect(() => {
    const fetchSectionData = async () => {
      if (!adminToken) return;
      if (
        activeSection !== 'users'
        && activeSection !== 'agents'
        && activeSection !== 'chats'
        && activeSection !== 'turnkeyRequests'
        && activeSection !== 'errorReports'
      ) return;

      try {
        setIsLoadingTable(true);
        setError('');
        if (activeSection === 'users') {
          const data = await adminService.getUsers(adminToken, {
            page: usersState.page,
            pageSize: usersState.pageSize,
            search: usersState.search,
          });
          setUsersState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'agents') {
          const data = await adminService.getAgents(adminToken, {
            page: agentsState.page,
            pageSize: agentsState.pageSize,
            search: agentsState.search,
          });
          setAgentsState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'turnkeyRequests') {
          const data = await adminService.getTurnkeyRequests(adminToken, {
            page: requestsState.page,
            pageSize: requestsState.pageSize,
            search: requestsState.search,
          });
          setRequestsState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'errorReports') {
          const data = await adminService.getErrorReports(adminToken, {
            page: errorReportsState.page,
            pageSize: errorReportsState.pageSize,
            search: errorReportsState.search,
          });
          setErrorReportsState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'chats') {
          const data = await adminService.getChats(adminToken, {
            page: chatsState.page,
            pageSize: chatsState.pageSize,
            search: chatsState.search,
            agentId: chatsState.agentId ? Number(chatsState.agentId) : null,
            agentUsername: chatsState.agentUsername,
          });
          const nextItems = data.items ?? [];
          setChatsState((prev) => ({
            ...prev,
            items: nextItems,
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
          setSelectedChatKey((prev) => {
            if (prev && nextItems.some((item) => item.chat_key === prev)) return prev;
            return nextItems[0]?.chat_key ?? null;
          });
        }
      } catch (err) {
        setError(formatError(err));
      } finally {
        setIsLoadingTable(false);
      }
    };
    fetchSectionData();
  }, [
    activeSection,
    adminToken,
    usersState.page,
    usersState.pageSize,
    usersState.search,
    agentsState.page,
    agentsState.pageSize,
    agentsState.search,
    requestsState.page,
    requestsState.pageSize,
    requestsState.search,
    errorReportsState.page,
    errorReportsState.pageSize,
    errorReportsState.search,
    chatsState.page,
    chatsState.pageSize,
    chatsState.search,
    chatsState.agentId,
    chatsState.agentUsername,
  ]);

  useEffect(() => {
    if (!adminToken) return;
    if (activeSection !== 'billing') return;

    let cancelled = false;
    const fetchPlans = async () => {
      try {
        setIsLoadingPlans(true);
        setError('');
        const data = await adminService.getPlans(adminToken);
        const plans = Array.isArray(data?.plans) ? data.plans : [];
        if (cancelled) return;
        setPlansDraft(
          plans.map((p) => ({
            code: p?.code,
            title: p?.title || p?.code,
            price_rub_month: Number(p?.price_rub_month ?? 0),
            max_active_agents: Number(p?.max_active_agents ?? 0),
            knowledge_base_chunk_limit:
              p?.knowledge_base_chunk_limit === null ? null : Number(p?.knowledge_base_chunk_limit ?? 0),
          }))
        );
      } catch (err) {
        if (!cancelled) setError(formatError(err));
      } finally {
        if (!cancelled) setIsLoadingPlans(false);
      }
    };

    fetchPlans();
    return () => {
      cancelled = true;
    };
  }, [activeSection, adminToken]);

  useEffect(() => {
    if (!adminToken) return;
    if (activeSection !== 'promoCodes') return;

    let cancelled = false;
    const fetchPromoCodes = async () => {
      try {
        setIsLoadingPromoCodes(true);
        setError('');
        const data = await adminService.getPromoCodes(adminToken);
        if (cancelled) return;
        setPromoCodes(Array.isArray(data?.items) ? data.items : []);
      } catch (err) {
        if (!cancelled) setError(formatError(err));
      } finally {
        if (!cancelled) setIsLoadingPromoCodes(false);
      }
    };

    fetchPromoCodes();
    return () => {
      cancelled = true;
    };
  }, [activeSection, adminToken]);

  // --- Content Publisher effects ---
  useEffect(() => {
    if (!adminToken || activeSection !== 'contentPublisher') return;
    let cancelled = false;

    const load = async () => {
      setApError('');
      if (apTab === 'settings') {
        try {
          setApIsLoadingSettings(true);
          const data = await adminService.apGetSettings(adminToken);
          if (cancelled) return;
          const s = data.settings ?? {};
          setApSettings(s);
          setApSettingsDraft({
            posting_enabled: s.posting_enabled ?? false,
            posting_frequency_hours: s.posting_frequency_hours ?? 24,
            vcru_enabled: s.vcru_enabled ?? false,
            vcru_email: s.vcru_email ?? '',
            vcru_password: '',
            vcru_subsite_id: s.vcru_subsite_id ?? '',
            zen_enabled: s.zen_enabled ?? false,
            zen_login: s.zen_login ?? '',
            zen_password: '',
            zen_channel_id: s.zen_channel_id ?? '',
            auto_topics_enabled: s.auto_topics_enabled ?? true,
            topic_categories: (s.topic_categories ?? []).join(', '),
            promo_ratio: s.promo_ratio ?? 60,
            company_name: s.company_name ?? 'RSD AI',
            company_url: s.company_url ?? '',
            company_description: s.company_description ?? '',
            article_min_words: s.article_min_words ?? 600,
            article_max_words: s.article_max_words ?? 1500,
          });
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingSettings(false);
        }
      } else if (apTab === 'topics') {
        try {
          setApIsLoadingTopics(true);
          const data = await adminService.apGetTopics(adminToken);
          if (cancelled) return;
          setApTopics(data.items ?? []);
          setApTopicsTotal(data.total ?? 0);
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingTopics(false);
        }
      } else if (apTab === 'images') {
        try {
          setApIsLoadingImages(true);
          const data = await adminService.apGetImages(adminToken);
          if (cancelled) return;
          setApImages(data.items ?? []);
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingImages(false);
        }
      } else if (apTab === 'jobs') {
        try {
          setApIsLoadingJobs(true);
          const data = await adminService.apGetJobs(adminToken);
          if (cancelled) return;
          setApJobs(data.items ?? []);
          setApJobsTotal(data.total ?? 0);
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingJobs(false);
        }
      }
    };

    load();
    return () => { cancelled = true; };
  }, [activeSection, adminToken, apTab]);

  useEffect(() => {
    if (!adminToken || activeSection !== 'salesDepartment') return;
    let cancelled = false;
    const load = async () => {
      try {
        setSalesDeptLoading(true);
        setError('');
        const [team, funnel] = await Promise.all([
          adminService.salesGetTeam(adminToken),
          adminService.salesGetFunnel(adminToken),
        ]);
        if (cancelled) return;
        setSalesDeptMembers(team.items ?? []);
        setSalesDeptFunnel(funnel);
      } catch (err) {
        if (!cancelled) setError(formatError(err));
      } finally {
        if (!cancelled) setSalesDeptLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [adminToken, activeSection]);

  useEffect(() => {
    if (!salesToken) {
      setSalesMe(null);
      setSalesContacts({ items: [], page: 1, totalPages: 1, total: 0 });
      setSalesContactsScope('active');
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        setSalesDeskLoading(true);
        setSalesDeskError('');
        const me = await salesService.getMe(salesToken);
        if (cancelled) return;
        setSalesMe(me);
        if (salesSection === 'desk') {
          const cdata = await salesService.getContacts(salesToken, {
            page: 1,
            pageSize: 50,
            archived: salesContactsScope === 'archive',
          });
          if (cancelled) return;
          setSalesContacts({
            items: cdata.items ?? [],
            page: cdata.page ?? 1,
            totalPages: cdata.total_pages ?? 1,
            total: cdata.total ?? 0,
          });
        } else if (salesSection === 'team' && me.member?.role === 'rop') {
          const [team, funnel] = await Promise.all([
            salesService.mgmtGetTeam(salesToken),
            salesService.mgmtGetFunnel(salesToken),
          ]);
          if (cancelled) return;
          setSalesDeptMembers(team.items ?? []);
          setSalesDeptFunnel(funnel);
        }
      } catch (err) {
        if (!cancelled) {
          setSalesDeskError(formatError(err));
          localStorage.removeItem(SALES_TOKEN_KEY);
          setSalesToken('');
          setSalesMe(null);
        }
      } finally {
        if (!cancelled) setSalesDeskLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [salesToken, salesSection, salesContactsScope]);

  const handleApSaveSettings = async (e) => {
    e.preventDefault();
    try {
      setApIsSavingSettings(true);
      setApError('');
      setApSuccess('');
      const cats = (apSettingsDraft.topic_categories || '')
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean);
      const payload = {
        ...apSettingsDraft,
        topic_categories: cats,
      };
      if (!payload.vcru_password) delete payload.vcru_password;
      if (!payload.zen_password) delete payload.zen_password;
      const data = await adminService.apUpdateSettings(adminToken, payload);
      const s = data.settings ?? {};
      setApSettings(s);
      setApSuccess('Настройки сохранены');
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApIsSavingSettings(false);
    }
  };

  const handleApAddTopics = async (e) => {
    e.preventDefault();
    const lines = apNewTopicsText.split('\n').map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    try {
      setApActionInProgress('add-topics');
      setApError('');
      await adminService.apAddTopics(adminToken, lines);
      setApNewTopicsText('');
      const data = await adminService.apGetTopics(adminToken);
      setApTopics(data.items ?? []);
      setApTopicsTotal(data.total ?? 0);
      setApSuccess(`Добавлено тем: ${lines.length}`);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApGenerateTopics = async () => {
    try {
      setApActionInProgress('gen-topics');
      setApError('');
      const data = await adminService.apGenerateTopics(adminToken, { count: 10 });
      const refreshed = await adminService.apGetTopics(adminToken);
      setApTopics(refreshed.items ?? []);
      setApTopicsTotal(refreshed.total ?? 0);
      setApSuccess(`Сгенерировано тем: ${data.added ?? 0}`);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApDeleteTopic = async (id) => {
    if (!window.confirm('Удалить тему?')) return;
    try {
      setApActionInProgress(`del-topic-${id}`);
      setApError('');
      await adminService.apDeleteTopic(adminToken, id);
      setApTopics((prev) => prev.filter((t) => t.id !== id));
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApUploadImages = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    try {
      setApActionInProgress('upload-images');
      setApError('');
      for (const file of files) {
        await adminService.apUploadImage(adminToken, file);
      }
      const data = await adminService.apGetImages(adminToken);
      setApImages(data.items ?? []);
      setApSuccess(`Загружено изображений: ${files.length}`);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
      e.target.value = '';
    }
  };

  const handleApDeleteImage = async (id) => {
    if (!window.confirm('Удалить изображение?')) return;
    try {
      setApActionInProgress(`del-img-${id}`);
      setApError('');
      await adminService.apDeleteImage(adminToken, id);
      setApImages((prev) => prev.filter((img) => img.id !== id));
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApRunNow = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    try {
      setApActionInProgress('run-now');
      setApError('');
      setApSuccess('');
      const data = await adminService.apRunNow(adminToken, {
        platform: apRunNowPlatform || undefined,
        topic: apRunNowTopic || undefined,
      });
      setApSuccess(`Задача создана! job_id=${data.job_id}, платформа: ${data.platform}, тема: "${data.topic}"`);
      setApRunNowTopic('');
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApPreview = async (e) => {
    e.preventDefault();
    if (!apPreviewTopic.trim()) return;
    try {
      setApActionInProgress('preview');
      setApError('');
      setApPreviewResult(null);
      const data = await adminService.apPreviewArticle(adminToken, {
        topic: apPreviewTopic.trim(),
        platform: 'vcru',
      });
      setApPreviewResult(data);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    if (!login.trim() || !password) {
      setError('Введите логин и пароль администратора');
      return;
    }

    try {
      setIsSubmitting(true);
      setError('');
      localStorage.removeItem(SALES_TOKEN_KEY);
      setSalesToken('');
      const response = await adminService.login(login.trim(), password);
      const token = response?.access_token;
      if (!token) {
        setError('Сервер не вернул токен администратора');
        return;
      }
      localStorage.setItem(ADMIN_TOKEN_KEY, token);
      setAdminToken(token);
      setPassword('');
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSalesLogin = async (event) => {
    event.preventDefault();
    if (!login.trim() || !password) {
      setError('Введите логин и пароль');
      return;
    }
    try {
      setIsSubmitting(true);
      setError('');
      localStorage.removeItem(ADMIN_TOKEN_KEY);
      setAdminToken('');
      setStats(null);
      const response = await salesService.login(login.trim(), password);
      const token = response?.access_token;
      if (!token) {
        setError('Сервер не вернул токен');
        return;
      }
      localStorage.setItem(SALES_TOKEN_KEY, token);
      setSalesToken(token);
      setPassword('');
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSalesLogout = () => {
    localStorage.removeItem(SALES_TOKEN_KEY);
    setSalesToken('');
    setSalesMe(null);
    setSalesSection('desk');
    setSalesDeskError('');
    setPassword('');
  };

  const handleLogout = () => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    setAdminToken('');
    setStats(null);
    setError('');
    setPassword('');
  };

  const handleSavePlans = async () => {
    try {
      setIsSavingPlans(true);
      setError('');

      const payloadPlans = (plansDraft || []).map((p) => ({
        code: p.code,
        price_rub_month: Number(p.price_rub_month ?? 0),
        max_active_agents: Number(p.max_active_agents ?? 0),
        knowledge_base_chunk_limit:
          p.knowledge_base_chunk_limit === null ? null : Number(p.knowledge_base_chunk_limit ?? 0),
      }));

      const data = await adminService.updatePlans(adminToken, payloadPlans);
      const updatedPlans = Array.isArray(data?.plans) ? data.plans : [];
      setPlansDraft(
        updatedPlans.map((p) => ({
          code: p?.code,
          title: p?.title || p?.code,
          price_rub_month: Number(p?.price_rub_month ?? 0),
          max_active_agents: Number(p?.max_active_agents ?? 0),
          knowledge_base_chunk_limit:
            p?.knowledge_base_chunk_limit === null
              ? null
              : Number(p?.knowledge_base_chunk_limit ?? 0),
        }))
      );
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsSavingPlans(false);
    }
  };

  const refreshUsers = async () => {
    try {
      setIsLoadingTable(true);
      setError('');
      const data = await adminService.getUsers(adminToken, {
        page: usersState.page,
        pageSize: usersState.pageSize,
        search: usersState.search,
      });
      setUsersState((prev) => ({
        ...prev,
        items: data.items ?? [],
        total: data.pagination?.total ?? 0,
        totalPages: data.pagination?.total_pages ?? 1,
      }));
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsLoadingTable(false);
    }
  };

  const handleBanUser = async (user) => {
    const action = user.is_banned ? 'unban' : 'ban';
    const confirmMsg = user.is_banned
      ? `Разблокировать пользователя "${user.name}"?`
      : `Заблокировать пользователя "${user.name}"? Все агенты будут удалены.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setActionInProgress(user.id);
      setError('');
      if (action === 'ban') {
        await adminService.banUser(adminToken, user.id);
      } else {
        await adminService.unbanUser(adminToken, user.id);
      }
      await refreshUsers();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleGiftSubscription = async () => {
    const { user, planCode } = giftModal;
    if (!user || !planCode) return;

    try {
      setActionInProgress(user.id);
      setError('');
      await adminService.giftSubscription(adminToken, user.id, planCode);
      setGiftModal({ open: false, user: null, planCode: 'Advanced' });
      await refreshUsers();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const refreshPromoCodes = async () => {
    try {
      setIsLoadingPromoCodes(true);
      setError('');
      const data = await adminService.getPromoCodes(adminToken);
      setPromoCodes(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsLoadingPromoCodes(false);
    }
  };

  const handleCreatePromoCode = async (event) => {
    event.preventDefault();
    const code = promoCodeDraft.code.trim().toUpperCase();
    const discountPercent = Number(promoCodeDraft.discountPercent);
    if (!code) {
      setError('Введите промокод');
      return;
    }
    if (Number.isNaN(discountPercent) || discountPercent < 0 || discountPercent > 100) {
      setError('Скидка должна быть от 0 до 100');
      return;
    }

    try {
      setActionInProgress('promo-create');
      setError('');
      await adminService.createPromoCode(adminToken, {
        code,
        discount_percent: discountPercent,
      });
      setPromoCodeDraft({ code: '', discountPercent: 0 });
      await refreshPromoCodes();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDeletePromoCode = async (promoCodeItem) => {
    if (!window.confirm(`Удалить промокод "${promoCodeItem.code}"?`)) return;

    try {
      setActionInProgress(`promo-delete-${promoCodeItem.id}`);
      setError('');
      await adminService.deletePromoCode(adminToken, promoCodeItem.id);
      await refreshPromoCodes();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleSendEmailBroadcast = async (event) => {
    event.preventDefault();
    const subject = broadcastDraft.subject.trim();
    const body = broadcastDraft.body.trim();
    if (subject.length < 3) {
      setError('Тема письма должна быть не короче 3 символов');
      return;
    }
    if (body.length < 10) {
      setError('Текст рассылки должен быть не короче 10 символов');
      return;
    }
    const interval = Number(broadcastIntervalSeconds);
    if (Number.isNaN(interval) || interval < 30) {
      setError('Интервал между письмами — не меньше 30 секунд');
      return;
    }
    if (
      !window.confirm(
        `Запустить рассылку по всем с подтверждённым email? Пауза между письмами: ${interval} с.`
      )
    ) {
      return;
    }

    try {
      setActionInProgress('email-broadcast');
      setError('');
      setBroadcastJobStatus(null);
      const result = await adminService.sendEmailBroadcast(adminToken, {
        subject,
        body,
        interval_seconds: Math.min(Math.max(Math.round(interval), 30), 86400),
      });
      setBroadcastJobId(result.job_id);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  useEffect(() => {
    const jobId = targetedJobId || broadcastJobId;
    if (!jobId || !adminToken) {
      return undefined;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const job = await adminService.getEmailTargetedBroadcastJob(adminToken, jobId);
        if (cancelled) return;
        if (job.kind === 'all_verified') {
          setBroadcastJobStatus(job);
        } else {
          setTargetedJobStatus(job);
        }
        if (job.status === 'completed' || job.status === 'failed') {
          if (job.kind === 'all_verified') {
            setBroadcastJobId(null);
          } else {
            setTargetedJobId(null);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(formatError(err));
          setTargetedJobId((prev) => (prev === jobId ? null : prev));
          setBroadcastJobId((prev) => (prev === jobId ? null : prev));
        }
      }
    };
    poll();
    const interval = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [targetedJobId, broadcastJobId, adminToken]);

  const addTargetedGroup = () => {
    const n = targetedGroupIdRef.current;
    targetedGroupIdRef.current = n + 1;
    setTargetedGroups((prev) => [
      ...prev,
      { id: `g${n}`, title: `Группа ${n}`, emailsRaw: '', selected: true },
    ]);
  };

  const removeTargetedGroup = (groupId) => {
    setTargetedGroups((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((g) => g.id !== groupId);
    });
  };

  const buildTargetedPayload = () => {
    const groups = targetedGroups.map((g) => ({
      title: g.title.trim(),
      emails_raw: g.emailsRaw,
    }));
    const selected_titles = targetedGroups
      .filter((g) => g.selected && g.title.trim())
      .map((g) => g.title.trim());
    return { groups, selected_titles };
  };

  const handleTargetedPreview = async (event) => {
    event.preventDefault();
    const { groups, selected_titles } = buildTargetedPayload();
    if (!selected_titles.length) {
      setError('Отметьте хотя бы одну группу с непустым названием');
      return;
    }
    const emptyTitle = groups.some((g) => !g.title);
    if (emptyTitle) {
      setError('У каждой группы должно быть название');
      return;
    }
    try {
      setTargetedPreviewLoading(true);
      setError('');
      const data = await adminService.previewEmailTargeted(adminToken, { groups, selected_titles });
      setTargetedPreview(data);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setTargetedPreviewLoading(false);
    }
  };

  const handleTargetedSend = async (event) => {
    event.preventDefault();
    const subject = targetedBroadcastDraft.subject.trim();
    const body = targetedBroadcastDraft.body.trim();
    if (subject.length < 3) {
      setError('Тема письма (точечная рассылка) — не короче 3 символов');
      return;
    }
    if (body.length < 10) {
      setError('Текст письма — не короче 10 символов');
      return;
    }
    const interval = Number(targetedIntervalSeconds);
    if (Number.isNaN(interval) || interval < 30) {
      setError('Интервал между письмами — не меньше 30 секунд');
      return;
    }
    const { groups, selected_titles } = buildTargetedPayload();
    if (!selected_titles.length) {
      setError('Отметьте хотя бы одну группу');
      return;
    }
    if (groups.some((g) => !g.title)) {
      setError('У каждой группы должно быть название');
      return;
    }
    if (
      !window.confirm(
        `Запустить точечную рассылку? Получатели: после разбора списков — смотрите превью. Пауза между письмами: ${interval} с.`
      )
    ) {
      return;
    }
    try {
      setActionInProgress('email-targeted');
      setError('');
      setTargetedJobStatus(null);
      const result = await adminService.sendEmailTargetedBroadcast(adminToken, {
        groups,
        selected_titles,
        subject,
        body,
        interval_seconds: Math.min(Math.max(Math.round(interval), 30), 86400),
      });
      setTargetedJobId(result.job_id);
      setTargetedPreview((prev) => ({
        ...(prev || {}),
        unique_total: result.total_recipients,
        per_group: result.preview?.per_group || prev?.per_group,
      }));
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const renderOverview = () => (
    <>
      <div className="management-content-head">
        <h2>Сводная статистика</h2>
        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoadingStats}
          onClick={async () => {
            try {
              setIsLoadingStats(true);
              setError('');
              const data = await adminService.getStats(adminToken);
              setStats(data);
            } catch (err) {
              setError(formatError(err));
            } finally {
              setIsLoadingStats(false);
            }
          }}
        >
          Обновить
        </button>
      </div>

      {error && <div className="management-error">{error}</div>}

      {isLoadingStats ? (
        <p>Загрузка статистики...</p>
      ) : (
        <>
          <div className="management-stats-grid">
            {statsCards.map((card) => (
              <article key={card.key} className="management-stat-card">
                <span>{card.title}</span>
                <strong>{card.value}</strong>
              </article>
            ))}
          </div>
          <h3 className="management-section-title">Пользователи по тарифам</h3>
          <div className="management-stats-grid management-plan-grid">
            {planCards.map((card) => (
              <article key={card.key} className="management-stat-card">
                <span>{card.title}</span>
                <strong>{card.value}</strong>
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );

  const renderUsers = () => (
    <>
      <div className="management-content-head">
        <h2>Пользователи</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по имени или Telegram ID"
            value={usersState.search}
            onChange={(e) => setUsersState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка пользователей...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Имя</th>
                  <th>Telegram ID</th>
                  <th>Тариф</th>
                  <th>Подписка до</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {usersState.items.map((user) => (
                  <tr key={user.id} className={user.is_banned ? 'management-row-banned' : ''}>
                    <td>{user.id}</td>
                    <td>{user.name}</td>
                    <td>{user.telegram_id ?? '-'}</td>
                    <td>{user.subscription_type}</td>
                    <td>
                      {user.subscription_end_date
                        ? new Date(user.subscription_end_date).toLocaleDateString()
                        : '-'}
                    </td>
                    <td>
                      {user.is_banned
                        ? <span className="management-badge management-badge-banned">Заблокирован</span>
                        : <span className="management-badge management-badge-active">Активен</span>}
                    </td>
                    <td className="management-actions-cell">
                      <button
                        type="button"
                        className={`btn btn-sm ${user.is_banned ? 'btn-outline' : 'btn-danger'}`}
                        disabled={actionInProgress === user.id}
                        onClick={() => handleBanUser(user)}
                      >
                        {actionInProgress === user.id ? '...' : user.is_banned ? 'Разбан' : 'Бан'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline"
                        disabled={actionInProgress === user.id || user.is_banned}
                        onClick={() => setGiftModal({ open: true, user, planCode: 'Advanced' })}
                      >
                        Подарить
                      </button>
                    </td>
                  </tr>
                ))}
                {usersState.items.length === 0 && (
                  <tr><td colSpan={7}>Ничего не найдено</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={usersState.page <= 1}
              onClick={() => setUsersState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {usersState.page} из {usersState.totalPages} (всего: {usersState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={usersState.page >= usersState.totalPages}
              onClick={() => setUsersState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}

      {giftModal.open && (
        <div className="management-modal-overlay" onClick={() => setGiftModal({ open: false, user: null, planCode: 'Advanced' })}>
          <div className="management-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Подарить подписку</h3>
            <p>Пользователь: <strong>{giftModal.user?.name}</strong> (ID: {giftModal.user?.id})</p>
            <div className="management-form-row">
              <label>Тариф</label>
              <select
                value={giftModal.planCode}
                onChange={(e) => setGiftModal((prev) => ({ ...prev, planCode: e.target.value }))}
              >
                <option value="Advanced">Advanced</option>
                <option value="Pro">Pro</option>
              </select>
            </div>
            <p className="management-modal-hint">Подписка будет продлена на 30 дней от текущей даты окончания (или от сегодня).</p>
            <div className="management-modal-buttons">
              <button
                type="button"
                className="btn btn-black"
                disabled={actionInProgress === giftModal.user?.id}
                onClick={handleGiftSubscription}
              >
                {actionInProgress === giftModal.user?.id ? 'Оформляю...' : 'Подарить'}
              </button>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setGiftModal({ open: false, user: null, planCode: 'Advanced' })}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  const renderAgents = () => (
    <>
      <div className="management-content-head">
        <h2>Агенты</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по username, owner, bot_id"
            value={agentsState.search}
            onChange={(e) => setAgentsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка агентов...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Bot ID</th>
                  <th>Username</th>
                  <th>Владелец</th>
                  <th>Тариф</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {agentsState.items.map((agent) => (
                  <tr key={agent.id}>
                    <td>{agent.id}</td>
                    <td>{agent.bot_id ?? '-'}</td>
                    <td>{agent.bot_username ?? '-'}</td>
                    <td>{agent.owner_name}</td>
                    <td>{agent.owner_subscription_type}</td>
                    <td>{agent.is_active ? 'Активен' : 'Выключен'}</td>
                  </tr>
                ))}
                {agentsState.items.length === 0 && (
                  <tr><td colSpan={6}>Ничего не найдено</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={agentsState.page <= 1}
              onClick={() => setAgentsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {agentsState.page} из {agentsState.totalPages} (всего: {agentsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={agentsState.page >= agentsState.totalPages}
              onClick={() => setAgentsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const selectedChat = chatsState.items.find((item) => item.chat_key === selectedChatKey) || null;

  const renderChats = () => (
    <>
      <div className="management-content-head">
        <h2>Чаты всех агентов</h2>
        <div className="management-inline-controls management-inline-controls-grid">
          <input
            type="text"
            placeholder="Поиск по пользователю, username агента или external_id"
            value={chatsState.search}
            onChange={(e) => setChatsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
          <input
            type="number"
            min={1}
            placeholder="ID агента"
            value={chatsState.agentId}
            onChange={(e) => setChatsState((prev) => ({ ...prev, page: 1, agentId: e.target.value }))}
          />
          <input
            type="text"
            placeholder="Username агента"
            value={chatsState.agentUsername}
            onChange={(e) => setChatsState((prev) => ({ ...prev, page: 1, agentUsername: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка чатов...</p> : (
        <>
          <div className="management-chats-layout">
            <aside className="management-chats-list">
              {chatsState.items.length === 0 ? (
                <p className="management-chat-empty">Чаты не найдены</p>
              ) : (
                chatsState.items.map((chat) => (
                  <button
                    key={chat.chat_key}
                    type="button"
                    className={`management-chat-item ${selectedChatKey === chat.chat_key ? 'active' : ''}`}
                    onClick={() => setSelectedChatKey(chat.chat_key)}
                  >
                    <div className="management-chat-item-top">
                      <strong>{chat.user_display_name || `User ${chat.user_external_id}`}</strong>
                      {chat.is_frozen ? <span className="management-badge management-badge-banned">Заморожен</span> : null}
                    </div>
                    <div className="management-chat-item-meta">
                      <span>@{chat.agent_bot_username || 'unknown_agent'} · {formatChatChannel(chat.chat_channel)}</span>
                      <span>{chat.last_message_at ? new Date(chat.last_message_at).toLocaleString() : '—'}</span>
                    </div>
                  </button>
                ))
              )}
            </aside>
            <section className="management-chat-thread">
              {!selectedChat ? (
                <p className="management-chat-empty">Выберите чат слева для просмотра переписки</p>
              ) : (
                <>
                  <div className="management-chat-thread-head">
                    <div className="management-cell-stack">
                      <strong>{selectedChat.user_display_name || `User ${selectedChat.user_external_id}`}</strong>
                      <span className="management-cell-muted">
                        Агент: @{selectedChat.agent_bot_username || 'unknown_agent'} ·
                        {' '}
                        {formatChatChannel(selectedChat.chat_channel)}
                        {' '}
                        · external_id:
                        {' '}
                        {selectedChat.user_external_id}
                      </span>
                    </div>
                    <span className="management-cell-muted">
                      Сообщений пользователя:
                      {' '}
                      {selectedChat.questions_count ?? 0}
                    </span>
                  </div>
                  <div className="management-chat-messages">
                    {(selectedChat.messages || []).length === 0 ? (
                      <p className="management-chat-empty">Сообщений в чате пока нет</p>
                    ) : (
                      selectedChat.messages.map((message, index) => (
                        <article
                          key={`${selectedChat.chat_key}-${index}-${message.created_at || 'no-time'}`}
                          className={`management-chat-message ${message.role === 'user' ? 'user' : 'operator'}`}
                        >
                          <header>
                            <span>
                              {message.role === 'user' ? 'Пользователь' : message.role === 'operator' ? 'Оператор' : 'Агент'}
                              {' '}
                              ·
                              {' '}
                              {formatChatChannel(message.channel)}
                            </span>
                            <time>{message.created_at ? new Date(message.created_at).toLocaleString() : '—'}</time>
                          </header>
                          <p>{message.text || '—'}</p>
                        </article>
                      ))
                    )}
                  </div>
                </>
              )}
            </section>
          </div>

          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={chatsState.page <= 1}
              onClick={() => setChatsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {chatsState.page} из {chatsState.totalPages} (всего: {chatsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={chatsState.page >= chatsState.totalPages}
              onClick={() => setChatsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const renderErrorReports = () => (
    <>
      <div className="management-content-head">
        <h2>Сообщения об ошибках</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по тексту, имени или email"
            value={errorReportsState.search}
            onChange={(e) => setErrorReportsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка сообщений...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table management-table-wrap-text">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Дата</th>
                  <th>Пользователь</th>
                  <th>Описание</th>
                </tr>
              </thead>
              <tbody>
                {errorReportsState.items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.created_at ? new Date(row.created_at).toLocaleString() : '-'}</td>
                    <td>
                      <div className="management-cell-stack">
                        <span>{row.user?.name ?? '—'}</span>
                        <span className="management-cell-muted">{row.user?.email || '—'}</span>
                      </div>
                    </td>
                    <td>{row.description}</td>
                  </tr>
                ))}
                {errorReportsState.items.length === 0 && (
                  <tr><td colSpan={4}>Сообщений пока нет</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={errorReportsState.page <= 1}
              onClick={() => setErrorReportsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {errorReportsState.page} из {errorReportsState.totalPages} (всего: {errorReportsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={errorReportsState.page >= errorReportsState.totalPages}
              onClick={() => setErrorReportsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const renderTurnkeyRequests = () => (
    <>
      <div className="management-content-head">
        <h2>Заявки по тарифу «Агент под ключ»</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по телефону, email или тексту заявки"
            value={requestsState.search}
            onChange={(e) => setRequestsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка заявок...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table management-table-wrap-text">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Дата</th>
                  <th>Телефон</th>
                  <th>Email</th>
                  <th>Запрос</th>
                </tr>
              </thead>
              <tbody>
                {requestsState.items.map((request) => (
                  <tr key={request.id}>
                    <td>{request.id}</td>
                    <td>{request.created_at ? new Date(request.created_at).toLocaleString() : '-'}</td>
                    <td>{request.phone_number}</td>
                    <td>{request.email}</td>
                    <td>{request.requested_agent || request.purpose}</td>
                  </tr>
                ))}
                {requestsState.items.length === 0 && (
                  <tr><td colSpan={5}>Заявок пока нет</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={requestsState.page <= 1}
              onClick={() => setRequestsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {requestsState.page} из {requestsState.totalPages} (всего: {requestsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={requestsState.page >= requestsState.totalPages}
              onClick={() => setRequestsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const renderBilling = () => (
    <>
      <div className="management-content-head">
        <h2>Тарифы</h2>
        <button
          type="button"
          className="btn btn-outline"
          disabled={isSavingPlans || isLoadingPlans || (plansDraft || []).length === 0}
          onClick={handleSavePlans}
        >
          Сохранить изменения
        </button>
      </div>

      {error && <div className="management-error">{error}</div>}

      {isLoadingPlans ? (
        <p>Загрузка тарифов...</p>
      ) : (
        <div className="management-plans-editor">
          {(plansDraft || []).map((plan) => {
            const kbUnlimited = plan.knowledge_base_chunk_limit === null;
            return (
              <article key={plan.code} className="management-plan-editor-card">
                <h3>{plan.title}</h3>

                <div className="management-form-row">
                  <label>Цена (руб/мес)</label>
                  <input
                    type="number"
                    min={0}
                    value={plan.price_rub_month}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setPlansDraft((prev) =>
                        prev.map((p) =>
                          p.code === plan.code ? { ...p, price_rub_month: Number.isNaN(val) ? 0 : val } : p
                        )
                      );
                    }}
                  />
                </div>

                <div className="management-form-row">
                  <label>Макс. активных агентов</label>
                  <input
                    type="number"
                    min={0}
                    value={plan.max_active_agents}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setPlansDraft((prev) =>
                        prev.map((p) =>
                          p.code === plan.code ? { ...p, max_active_agents: Number.isNaN(val) ? 0 : val } : p
                        )
                      );
                    }}
                  />
                </div>

                <div className="management-form-row">
                  <label className="management-checkbox">
                    <input
                      type="checkbox"
                      checked={kbUnlimited}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setPlansDraft((prev) =>
                          prev.map((p) => {
                            if (p.code !== plan.code) return p;
                            if (checked) return { ...p, knowledge_base_chunk_limit: null };
                            // If leaving unlimited mode, restore a sane default.
                            return {
                              ...p,
                              knowledge_base_chunk_limit: p.knowledge_base_chunk_limit ?? 100,
                            };
                          })
                        );
                      }}
                    />
                    Безлимит базы знаний
                  </label>

                  <input
                    type="number"
                    min={0}
                    disabled={kbUnlimited}
                    value={kbUnlimited ? '' : plan.knowledge_base_chunk_limit ?? 0}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setPlansDraft((prev) =>
                        prev.map((p) =>
                          p.code === plan.code
                            ? { ...p, knowledge_base_chunk_limit: Number.isNaN(val) ? 0 : val }
                            : p
                        )
                      );
                    }}
                    placeholder="Лимит чанков"
                  />
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );

  const renderPromoCodes = () => (
    <>
      <div className="management-content-head">
        <h2>Промокоды</h2>
        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoadingPromoCodes || actionInProgress === 'promo-create'}
          onClick={refreshPromoCodes}
        >
          Обновить
        </button>
      </div>
      {error && <div className="management-error">{error}</div>}

      <form className="management-promo-form" onSubmit={handleCreatePromoCode}>
        <div className="management-form-row">
          <label htmlFor="promo-code-input">Промокод</label>
          <input
            id="promo-code-input"
            type="text"
            placeholder="Например: SPRING50"
            value={promoCodeDraft.code}
            maxLength={64}
            onChange={(e) => setPromoCodeDraft((prev) => ({ ...prev, code: e.target.value.toUpperCase() }))}
          />
        </div>
        <div className="management-form-row">
          <label htmlFor="promo-discount-input">Скидка (%)</label>
          <input
            id="promo-discount-input"
            type="number"
            min={0}
            max={100}
            value={promoCodeDraft.discountPercent}
            onChange={(e) => setPromoCodeDraft((prev) => ({ ...prev, discountPercent: e.target.value }))}
          />
        </div>
        <button
          type="submit"
          className="btn btn-black"
          disabled={actionInProgress === 'promo-create'}
        >
          {actionInProgress === 'promo-create' ? 'Создание...' : 'Добавить промокод'}
        </button>
      </form>

      {isLoadingPromoCodes ? (
        <p>Загрузка промокодов...</p>
      ) : (
        <div className="management-table-wrap">
          <table className="management-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Код</th>
                <th>Скидка</th>
                <th>Создан</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {promoCodes.map((promoCodeItem) => (
                <tr key={promoCodeItem.id}>
                  <td>{promoCodeItem.id}</td>
                  <td>{promoCodeItem.code}</td>
                  <td>{promoCodeItem.discount_percent}%</td>
                  <td>
                    {promoCodeItem.created_at
                      ? new Date(promoCodeItem.created_at).toLocaleString()
                      : '-'}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      disabled={actionInProgress === `promo-delete-${promoCodeItem.id}`}
                      onClick={() => handleDeletePromoCode(promoCodeItem)}
                    >
                      {actionInProgress === `promo-delete-${promoCodeItem.id}` ? '...' : 'Удалить'}
                    </button>
                  </td>
                </tr>
              ))}
              {promoCodes.length === 0 && (
                <tr><td colSpan={5}>Промокодов пока нет</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  const refreshAdminSalesDept = async () => {
    if (!adminToken) return;
    try {
      setSalesDeptLoading(true);
      const [team, funnel] = await Promise.all([
        adminService.salesGetTeam(adminToken),
        adminService.salesGetFunnel(adminToken),
      ]);
      setSalesDeptMembers(team.items ?? []);
      setSalesDeptFunnel(funnel);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSalesDeptLoading(false);
    }
  };

  const handleAdminCreateSalesMember = async (e) => {
    e.preventDefault();
    try {
      setSalesTeamBusy('create');
      setError('');
      const sup = salesNewMember.supervisor_id.trim();
      await adminService.salesCreateMember(adminToken, {
        login: salesNewMember.login.trim(),
        password: salesNewMember.password,
        role: salesNewMember.role,
        supervisor_id: sup === '' ? null : Number(sup),
      });
      setSalesNewMember({ login: '', password: '', role: 'trainee', supervisor_id: '' });
      await refreshAdminSalesDept();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleAdminPatchSalesMember = async (memberId, patch) => {
    try {
      setSalesTeamBusy(`patch-a-${memberId}`);
      setError('');
      await adminService.salesUpdateMember(adminToken, memberId, patch);
      await refreshAdminSalesDept();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleAdminSalesExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setSalesTeamBusy('excel');
      setError('');
      const res = await adminService.salesUploadExcel(adminToken, file);
      await refreshAdminSalesDept();
      alert(res?.message || `Импортировано: ${res?.imported ?? 0}`);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
      e.target.value = '';
    }
  };

  const handleAdminManualContact = async (e) => {
    e.preventDefault();
    try {
      setSalesTeamBusy('manual-contact');
      setError('');
      await adminService.salesAddContactManual(adminToken, {
        org_name: (salesManualContact.org_name || salesManualContact.label || '').trim(),
      });
      setSalesManualContact({ org_name: '', label: '' });
      await refreshAdminSalesDept();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleAdminClearSalesCrm = async () => {
    if (
      !window.confirm(
        'Удалить все контакты локальной CRM (пул, назначённые, архив)? Учётные записи сотрудников и планы не затрагиваются. Сбросится дневная выдача контактов.'
      )
    ) {
      return;
    }
    try {
      setSalesTeamBusy('clear-crm');
      setError('');
      const res = await adminService.salesClearCrm(adminToken);
      await refreshAdminSalesDept();
      alert(res?.message || 'CRM очищена.');
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleRopPatchSalesMember = async (memberId, patch) => {
    try {
      setSalesTeamBusy(`patch-r-${memberId}`);
      setSalesDeskError('');
      await salesService.mgmtUpdateMember(salesToken, memberId, patch);
      const [team, funnel] = await Promise.all([
        salesService.mgmtGetTeam(salesToken),
        salesService.mgmtGetFunnel(salesToken),
      ]);
      setSalesDeptMembers(team.items ?? []);
      setSalesDeptFunnel(funnel);
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleRopCreateSalesMember = async (e) => {
    e.preventDefault();
    try {
      setSalesTeamBusy('rop-create');
      setSalesDeskError('');
      const sup = salesNewMember.supervisor_id.trim();
      await salesService.mgmtCreateMember(salesToken, {
        login: salesNewMember.login.trim(),
        password: salesNewMember.password,
        role: salesNewMember.role,
        supervisor_id: sup === '' ? null : Number(sup),
      });
      setSalesNewMember({ login: '', password: '', role: 'trainee', supervisor_id: '' });
      const [team, funnel] = await Promise.all([
        salesService.mgmtGetTeam(salesToken),
        salesService.mgmtGetFunnel(salesToken),
      ]);
      setSalesDeptMembers(team.items ?? []);
      setSalesDeptFunnel(funnel);
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleRopSalesExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setSalesTeamBusy('rop-excel');
      setSalesDeskError('');
      const res = await salesService.mgmtUploadExcel(salesToken, file);
      const [team, funnel] = await Promise.all([
        salesService.mgmtGetTeam(salesToken),
        salesService.mgmtGetFunnel(salesToken),
      ]);
      setSalesDeptMembers(team.items ?? []);
      setSalesDeptFunnel(funnel);
      alert(res?.message || `Импортировано: ${res?.imported ?? 0}`);
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
      e.target.value = '';
    }
  };

  const handleRopClearSalesCrm = async () => {
    if (
      !window.confirm(
        'Удалить все контакты локальной CRM (пул, назначённые, архив)? Учётные записи сотрудников и планы не затрагиваются. Сбросится дневная выдача контактов.'
      )
    ) {
      return;
    }
    try {
      setSalesTeamBusy('rop-clear-crm');
      setSalesDeskError('');
      const res = await salesService.mgmtClearCrm(salesToken);
      const [team, funnel] = await Promise.all([
        salesService.mgmtGetTeam(salesToken),
        salesService.mgmtGetFunnel(salesToken),
      ]);
      setSalesDeptMembers(team.items ?? []);
      setSalesDeptFunnel(funnel);
      alert(res?.message || 'CRM очищена.');
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleSalesSaveContact = async (contactId, body) => {
    if (!salesToken) return;
    try {
      setSalesTeamBusy(`save-contact-${contactId}`);
      setSalesDeskError('');
      await salesService.patchContact(salesToken, contactId, body);
      const cdata = await salesService.getContacts(salesToken, {
        page: 1,
        pageSize: 50,
        archived: salesContactsScope === 'archive',
      });
      setSalesContacts({
        items: cdata.items ?? [],
        page: cdata.page ?? 1,
        totalPages: cdata.total_pages ?? 1,
        total: cdata.total ?? 0,
      });
      const me = await salesService.getMe(salesToken);
      setSalesMe(me);
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const handleSalesRequestMore = async () => {
    if (!salesToken) return;
    try {
      setSalesTeamBusy('request-more');
      setSalesDeskError('');
      const res = await salesService.requestMoreContacts(salesToken);
      const [cdata, me] = await Promise.all([
        salesService.getContacts(salesToken, {
          page: 1,
          pageSize: 50,
          archived: salesContactsScope === 'archive',
        }),
        salesService.getMe(salesToken),
      ]);
      setSalesContacts({
        items: cdata.items ?? [],
        page: cdata.page ?? 1,
        totalPages: cdata.total_pages ?? 1,
        total: cdata.total ?? 0,
      });
      setSalesMe(me);
      alert(res?.message || `Назначено: ${res?.allocated ?? 0}`);
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const openSalesInvoiceModal = (contact) => {
    const org = contact?.org_name || '';
    setSalesInvoiceModal({
      open: true,
      contact,
      amountRub: '10000',
      serviceName: org ? `Услуги RSD для ${org}` : '',
      clientInn: '',
    });
  };

  const closeSalesInvoiceModal = () => {
    setSalesInvoiceModal({
      open: false,
      contact: null,
      amountRub: '10000',
      serviceName: '',
      clientInn: '',
    });
  };

  const handleSalesInvoiceSubmit = async (e) => {
    e.preventDefault();
    if (!salesToken || !salesInvoiceModal.contact) return;
    const contactId = salesInvoiceModal.contact.id;
    const amount = Number(String(salesInvoiceModal.amountRub).replace(',', '.'));
    if (!Number.isFinite(amount) || amount <= 0) {
      setSalesDeskError('Укажите корректную сумму в рублях');
      return;
    }
    try {
      setSalesTeamBusy(`invoice-${contactId}`);
      setSalesDeskError('');
      const { blob, receiptUuid } = await salesService.createInvoice(salesToken, contactId, {
        amountRub: amount,
        serviceName: salesInvoiceModal.serviceName.trim() || undefined,
        clientInn: salesInvoiceModal.clientInn.trim() || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chek_${contactId}${receiptUuid ? `_${receiptUuid.slice(0, 8)}` : ''}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      closeSalesInvoiceModal();
    } catch (err) {
      setSalesDeskError(formatError(err));
    } finally {
      setSalesTeamBusy(null);
    }
  };

  const renderFunnelSummary = (funnel) => {
    if (!funnel) return null;
    const keys = ['in_base', 'called', 'demo', 'closed', 'rejected', 'hesitating'];
    return (
      <div className="management-sales-funnel">
        {keys.map((k) => (
          <div key={k} className="management-sales-funnel-card">
            <span className="management-sales-funnel-label">{FUNNEL_LABELS[k]}</span>
            <span className="management-sales-funnel-value">{funnel[k] ?? 0}</span>
          </div>
        ))}
      </div>
    );
  };

  const renderSalesByMemberTable = (byMember) => {
    if (!Array.isArray(byMember) || !byMember.length) {
      return <p className="management-cell-muted">Нет данных по сотрудникам.</p>;
    }
    return (
      <div className="management-table-wrap">
        <table className="management-table">
          <thead>
            <tr>
              <th>Сотрудник</th>
              <th>Роль</th>
              <th>В базе</th>
              <th>В работе</th>
              <th>Демо</th>
              <th>Закрыто</th>
              <th>Отказ</th>
              <th>Сомневается</th>
            </tr>
          </thead>
          <tbody>
            {byMember.map((row) => (
              <tr key={row.member?.id}>
                <td>{row.member?.login}</td>
                <td>{SALES_ROLE_LABELS[row.member?.role] || row.member?.role}</td>
                <td>{row.funnel?.in_base ?? 0}</td>
                <td>{row.funnel?.called ?? 0}</td>
                <td>{row.funnel?.demo ?? 0}</td>
                <td>{row.funnel?.closed ?? 0}</td>
                <td>{row.funnel?.rejected ?? 0}</td>
                <td>{row.funnel?.hesitating ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderSalesDepartment = () => (
    <>
      <div className="management-content-head">
        <h2>Отдел продаж</h2>
        <p className="management-cell-muted">
          Общая локальная CRM: Excel и ручные контакты попадают в пул. Стажёру и МОПу сначала выдаётся
          половина дневной нормы (лимит задаёт админ или РОП). После проставления статусов всем в первой
          порции можно подгрузить остаток нормы. Раз в сутки (UTC) отработанные контакты уходят в архив при новой выдаче.
        </p>
      </div>
      {error && activeSection === 'salesDepartment' && <div className="management-error">{error}</div>}
      {salesDeptLoading ? (
        <p>Загрузка...</p>
      ) : (
        <>
          <h3>Общая воронка</h3>
          <p className="management-cell-muted">
            В общем пуле (ещё не назначено): <strong>{salesDeptFunnel?.crm_pool_available ?? 0}</strong>
          </p>
          {renderFunnelSummary(salesDeptFunnel?.total)}
          <h3 style={{ marginTop: '1.5rem' }}>По сотрудникам</h3>
          {renderSalesByMemberTable(salesDeptFunnel?.by_member)}

          <h3 style={{ marginTop: '1.5rem' }}>Новый сотрудник</h3>
          <form className="management-form-grid" onSubmit={handleAdminCreateSalesMember}>
            <label>
              Логин
              <input
                value={salesNewMember.login}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, login: e.target.value }))}
                required
              />
            </label>
            <label>
              Пароль
              <input
                type="password"
                value={salesNewMember.password}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, password: e.target.value }))}
                minLength={6}
                required
              />
            </label>
            <label>
              Роль
              <select
                value={salesNewMember.role}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, role: e.target.value }))}
              >
                <option value="trainee">Стажер</option>
                <option value="mop">МОП</option>
                <option value="rop">РОП</option>
              </select>
            </label>
            <label>
              ID руководителя (пусто для РОП)
              <input
                value={salesNewMember.supervisor_id}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, supervisor_id: e.target.value }))}
                placeholder="например 1"
              />
            </label>
            <div className="management-form-actions">
              <button type="submit" className="btn btn-black" disabled={salesTeamBusy === 'create'}>
                {salesTeamBusy === 'create' ? 'Создание...' : 'Добавить'}
              </button>
            </div>
          </form>

          <h3 style={{ marginTop: '1.5rem' }}>Планы и норма контактов</h3>
          <div className="management-table-wrap">
            <table className="management-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Логин</th>
                  <th>Роль</th>
                  <th>Руководитель</th>
                  <th>План прозвонов / мес</th>
                  <th>План демо / мес</th>
                  <th>План закрытий / мес</th>
                  <th>Контактов в день</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {salesDeptMembers.map((m) => (
                  <SalesMemberPlanRow
                    key={m.id}
                    member={m}
                    busy={salesTeamBusy === `patch-a-${m.id}`}
                    onSave={(id, patch) => handleAdminPatchSalesMember(id, patch)}
                  />
                ))}
                {salesDeptMembers.length === 0 && (
                  <tr>
                    <td colSpan={9}>Сотрудников пока нет</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <h3 style={{ marginTop: '1.5rem' }}>Загрузка Excel в общую базу</h3>
          <p className="management-cell-muted">
            Выберите файл .xlsx / .xls — контакты попадут в общий пул CRM, не на конкретного сотрудника.
          </p>
          <input type="file" accept=".xlsx,.xls" onChange={handleAdminSalesExcel} disabled={!!salesTeamBusy} />
          <div className="management-form-actions" style={{ marginTop: '0.75rem' }}>
            <button
              type="button"
              className="btn btn-danger"
              disabled={!!salesTeamBusy}
              onClick={handleAdminClearSalesCrm}
            >
              {salesTeamBusy === 'clear-crm' ? 'Очистка…' : 'Очистить CRM'}
            </button>
            <span className="management-cell-muted" style={{ alignSelf: 'center' }}>
              Пул, все назначения и архив. Сотрудников не удаляет.
            </span>
          </div>

          <h3 style={{ marginTop: '1.5rem' }}>Добавить контакт в общую базу</h3>
          <form className="management-form-grid" onSubmit={handleAdminManualContact}>
            <label>
              Название организации
              <input
                value={salesManualContact.org_name}
                onChange={(e) => setSalesManualContact((p) => ({ ...p, org_name: e.target.value }))}
                placeholder="Как в базе"
              />
            </label>
            <label>
              Подпись (устарело, необязательно)
              <input
                value={salesManualContact.label}
                onChange={(e) => setSalesManualContact((p) => ({ ...p, label: e.target.value }))}
                placeholder="если не заполнено название — можно сюда"
              />
            </label>
            <div className="management-form-actions">
              <button
                type="submit"
                className="btn btn-outline"
                disabled={salesTeamBusy === 'manual-contact'}
              >
                Добавить в базу
              </button>
            </div>
          </form>
        </>
      )}
    </>
  );

  const renderSalesStaffDesk = () => {
    const p = salesMe?.plan;
    const ach = salesMe?.achievement_month;
    return (
      <>
        <div className="management-content-head">
          <h2>
            Здравствуйте, {salesMe?.member?.login}{' '}
            <span className="management-cell-muted">
              ({SALES_ROLE_LABELS[salesMe?.member?.role] || salesMe?.member?.role})
            </span>
          </h2>
          <p className="management-cell-muted">Токен действует сутки; при истечении войдите снова.</p>
        </div>
        {salesDeskError && <div className="management-error">{salesDeskError}</div>}
        {salesDeskLoading ? (
          <p>Загрузка...</p>
        ) : (
          <>
            <h3>План на месяц</h3>
            <div className="management-stats-grid">
              <div className="management-stat-card">
                <span>Прозвоны</span>
                <strong>
                  {ach?.calls_done ?? 0} / {p?.calls_monthly ?? 0}
                </strong>
              </div>
              <div className="management-stat-card">
                <span>Демо</span>
                <strong>
                  {ach?.demos_done ?? 0} / {p?.demos_monthly ?? 0}
                </strong>
              </div>
              <div className="management-stat-card">
                <span>Закрытия</span>
                <strong>
                  {ach?.closes_done ?? 0} / {p?.closes_monthly ?? 0}
                </strong>
              </div>
              <div className="management-stat-card">
                <span>Норма в день</span>
                <strong>
                  {salesMe?.plan?.effective_daily_quota ?? 0}
                </strong>
                <span className="management-cell-muted" style={{ fontSize: 'var(--font-size-xs)', display: 'block', marginTop: 4 }}>
                  Из пула сегодня: {salesMe?.daily_pool_allocated ?? 0} / {salesMe?.plan?.effective_daily_quota ?? 0}
                  . Сначала половина нормы; когда всем проставлены статусы — кнопка ниже.
                </span>
              </div>
              <div className="management-stat-card">
                <span>Новых в работе</span>
                <strong>{salesMe?.pending_new_contacts ?? salesMe?.backlog_in_base ?? 0}</strong>
              </div>
              <div className="management-stat-card">
                <span>В общем пуле</span>
                <strong>{salesMe?.crm_pool_available ?? 0}</strong>
              </div>
            </div>
            {salesMe?.can_request_more && (
              <div className="management-form-actions" style={{ marginTop: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-black"
                  disabled={salesTeamBusy === 'request-more'}
                  onClick={handleSalesRequestMore}
                >
                  {salesTeamBusy === 'request-more' ? 'Загрузка...' : 'Подгрузить вторую половину нормы'}
                </button>
              </div>
            )}
            <h3 style={{ marginTop: '1.5rem' }}>Моя воронка</h3>
            {renderFunnelSummary(salesMe?.funnel_assigned)}
            <h3 style={{ marginTop: '1.5rem' }}>Мои контакты</h3>
            <div className="management-sales-contacts-tabs">
              <button
                type="button"
                className={salesContactsScope === 'active' ? 'btn btn-sm btn-black' : 'btn btn-sm btn-outline'}
                onClick={() => setSalesContactsScope('active')}
              >
                Активные
              </button>
              <button
                type="button"
                className={salesContactsScope === 'archive' ? 'btn btn-sm btn-black' : 'btn btn-sm btn-outline'}
                onClick={() => setSalesContactsScope('archive')}
              >
                Архив
              </button>
              <p className="management-sales-contacts-tabs-hint">
                В архиве контакты со сменённым статусом после нового дня (UTC). Активные — текущая работа.
              </p>
            </div>
            <div className="management-table-wrap management-table-wide">
              <table className="management-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Название</th>
                    <th>ФИО ЛПР</th>
                    <th>Тел. ЛПР</th>
                    <th>Тел. орг.</th>
                    <th>Моб.</th>
                    <th>Статус</th>
                    <th>Комментарий</th>
                    <th>Email</th>
                    <th>Сайт</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {salesContacts.items.map((c) => (
                    <SalesContactRow
                      key={c.id}
                      contact={c}
                      busy={salesTeamBusy}
                      onSaveRow={handleSalesSaveContact}
                      onInvoice={openSalesInvoiceModal}
                      readOnly={salesContactsScope === 'archive'}
                    />
                  ))}
                  {salesContacts.items.length === 0 && (
                    <tr>
                      <td colSpan={11}>
                        {salesContactsScope === 'archive'
                          ? 'Архив пуст.'
                          : 'Контактов нет — РОП/админ загрузит Excel или добавит вручную.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {salesInvoiceModal.open && salesInvoiceModal.contact && (
              <div className="management-modal-overlay" onClick={closeSalesInvoiceModal}>
                <div className="management-modal" onClick={(ev) => ev.stopPropagation()}>
                  <h3>Чек «Мой налог»</h3>
                  <p className="management-modal-hint">
                    Будет зарегистрирован доход самозанятого в «Мой налог» и скачан PDF чека.
                    Контакт: {salesInvoiceModal.contact.org_name || `#${salesInvoiceModal.contact.id}`}
                  </p>
                  <form className="management-form-grid" onSubmit={handleSalesInvoiceSubmit}>
                    <label>
                      Сумма, ₽
                      <input
                        type="number"
                        min="1"
                        step="0.01"
                        required
                        value={salesInvoiceModal.amountRub}
                        onChange={(ev) =>
                          setSalesInvoiceModal((p) => ({ ...p, amountRub: ev.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Наименование услуги
                      <input
                        type="text"
                        maxLength={512}
                        value={salesInvoiceModal.serviceName}
                        onChange={(ev) =>
                          setSalesInvoiceModal((p) => ({ ...p, serviceName: ev.target.value }))
                        }
                        placeholder="Услуги RSD для …"
                      />
                    </label>
                    <label>
                      ИНН организации (необязательно)
                      <input
                        type="text"
                        maxLength={12}
                        value={salesInvoiceModal.clientInn}
                        onChange={(ev) =>
                          setSalesInvoiceModal((p) => ({ ...p, clientInn: ev.target.value }))
                        }
                        placeholder="10 или 12 цифр для юрлица"
                      />
                    </label>
                    <div className="management-modal-buttons">
                      <button
                        type="button"
                        className="btn btn-outline"
                        onClick={closeSalesInvoiceModal}
                        disabled={!!salesTeamBusy}
                      >
                        Отмена
                      </button>
                      <button
                        type="submit"
                        className="btn btn-black"
                        disabled={!!salesTeamBusy}
                      >
                        {salesTeamBusy?.startsWith('invoice-') ? 'Создание…' : 'Создать и скачать PDF'}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </>
        )}
      </>
    );
  };

  const renderSalesStaffTeam = () => (
    <>
      <div className="management-content-head">
        <h2>Команда и воронка</h2>
      </div>
      {salesDeskError && <div className="management-error">{salesDeskError}</div>}
      {salesDeskLoading ? (
        <p>Загрузка...</p>
      ) : (
        <>
          <h3>Общая воронка команды</h3>
          {renderFunnelSummary(salesDeptFunnel?.total)}
          <h3 style={{ marginTop: '1.5rem' }}>По сотрудникам</h3>
          {renderSalesByMemberTable(salesDeptFunnel?.by_member)}

          <h3 style={{ marginTop: '1.5rem' }}>Новый сотрудник</h3>
          <form className="management-form-grid" onSubmit={handleRopCreateSalesMember}>
            <label>
              Логин
              <input
                value={salesNewMember.login}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, login: e.target.value }))}
                required
              />
            </label>
            <label>
              Пароль
              <input
                type="password"
                value={salesNewMember.password}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, password: e.target.value }))}
                minLength={6}
                required
              />
            </label>
            <label>
              Роль
              <select
                value={salesNewMember.role}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, role: e.target.value }))}
              >
                <option value="trainee">Стажер</option>
                <option value="mop">МОП</option>
              </select>
            </label>
            <label>
              ID руководителя (по умолчанию — вы)
              <input
                value={salesNewMember.supervisor_id}
                onChange={(e) => setSalesNewMember((p) => ({ ...p, supervisor_id: e.target.value }))}
                placeholder="оставьте пустым — будет вы"
              />
            </label>
            <div className="management-form-actions">
              <button type="submit" className="btn btn-black" disabled={salesTeamBusy === 'rop-create'}>
                {salesTeamBusy === 'rop-create' ? 'Создание...' : 'Добавить'}
              </button>
            </div>
          </form>

          <h3 style={{ marginTop: '1.5rem' }}>Планы команды</h3>
          <div className="management-table-wrap">
            <table className="management-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Логин</th>
                  <th>Роль</th>
                  <th>Руководитель</th>
                  <th>План прозвонов / мес</th>
                  <th>План демо / мес</th>
                  <th>План закрытий / мес</th>
                  <th>Контактов в день</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {salesDeptMembers
                  .filter((m) => m.id !== salesMe?.member?.id)
                  .map((m) => (
                    <SalesMemberPlanRow
                      key={m.id}
                      member={m}
                      busy={salesTeamBusy === `patch-r-${m.id}`}
                      onSave={(id, patch) => handleRopPatchSalesMember(id, patch)}
                    />
                  ))}
                {salesDeptMembers.filter((m) => m.id !== salesMe?.member?.id).length === 0 && (
                  <tr>
                    <td colSpan={9}>Подчинённых пока нет</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <h3 style={{ marginTop: '1.5rem' }}>Загрузка Excel в общую базу</h3>
          <p className="management-cell-muted">
            В пуле свободно: <strong>{salesDeptFunnel?.crm_pool_available ?? 0}</strong>
          </p>
          <input type="file" accept=".xlsx,.xls" onChange={handleRopSalesExcel} disabled={!!salesTeamBusy} />
          <div className="management-form-actions" style={{ marginTop: '0.75rem' }}>
            <button
              type="button"
              className="btn btn-danger"
              disabled={!!salesTeamBusy}
              onClick={handleRopClearSalesCrm}
            >
              {salesTeamBusy === 'rop-clear-crm' ? 'Очистка…' : 'Очистить CRM'}
            </button>
            <span className="management-cell-muted" style={{ alignSelf: 'center' }}>
              Пул, все назначения и архив. Сотрудников не удаляет.
            </span>
          </div>
        </>
      )}
    </>
  );

  const renderContentPublisher = () => {
    const AP_TABS = [
      { id: 'settings', label: 'Настройки' },
      { id: 'topics', label: 'Темы' },
      { id: 'images', label: 'Изображения' },
      { id: 'jobs', label: 'История' },
      { id: 'run', label: 'Запуск / Превью' },
    ];

    const statusLabel = (s) => ({
      pending: 'Ожидает',
      generating: 'Генерация',
      publishing: 'Публикация',
      published: 'Опубликовано',
      failed: 'Ошибка',
    }[s] || s);

    const statusClass = (s) => ({
      published: 'management-badge-success',
      failed: 'management-badge-danger',
      generating: 'management-badge-info',
      publishing: 'management-badge-info',
    }[s] || 'management-badge-muted');

    return (
      <>
        <div className="management-content-head">
          <h2>Контент — автопубликация статей</h2>
          <button
            type="button"
            className="btn btn-black"
            disabled={apActionInProgress === 'run-now'}
            onClick={handleApRunNow}
            title="Запустить автопубликацию сразу, без ожидания окна времени"
          >
            {apActionInProgress === 'run-now' ? 'Запуск...' : 'Выпустить статью сейчас'}
          </button>
        </div>

        {apError && <div className="management-error">{apError}</div>}
        {apSuccess && <div className="management-success">{apSuccess}</div>}

        <div className="ap-tabs">
          {AP_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`ap-tab-btn ${apTab === tab.id ? 'active' : ''}`}
              onClick={() => { setApTab(tab.id); setApError(''); setApSuccess(''); }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* SETTINGS TAB */}
        {apTab === 'settings' && (
          <div className="ap-panel">
            {apIsLoadingSettings ? <p>Загрузка настроек...</p> : (
              <form onSubmit={handleApSaveSettings} className="ap-settings-form">
                <section className="ap-section">
                  <h3>Расписание публикаций</h3>
                  <div className="management-form-row">
                    <label className="management-checkbox">
                      <input
                        type="checkbox"
                        checked={apSettingsDraft.posting_enabled ?? false}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, posting_enabled: e.target.checked }))}
                      />
                      Автопубликация включена
                    </label>
                  </div>
                  <div className="management-form-row">
                    <label>Частота (часов между постами)</label>
                    <input
                      type="number"
                      min={1}
                      max={720}
                      value={apSettingsDraft.posting_frequency_hours ?? 24}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, posting_frequency_hours: Number(e.target.value) }))}
                    />
                  </div>
                </section>

                <section className="ap-section">
                  <h3>Платформы</h3>

                  <div className="ap-platform-block">
                    <h4>vc.ru</h4>
                    <div className="management-form-row">
                      <label className="management-checkbox">
                        <input
                          type="checkbox"
                          checked={apSettingsDraft.vcru_enabled ?? false}
                          onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_enabled: e.target.checked }))}
                        />
                        Включить vc.ru
                      </label>
                    </div>
                    <div className="management-form-row">
                      <label>Email аккаунта</label>
                      <input
                        type="email"
                        placeholder="user@example.com"
                        value={apSettingsDraft.vcru_email ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_email: e.target.value }))}
                      />
                    </div>
                    <div className="management-form-row">
                      <label>
                        Пароль
                        {apSettings?.vcru_has_password && (
                          <span className="ap-hint"> (уже задан, оставьте пустым чтобы не менять)</span>
                        )}
                      </label>
                      <input
                        type="password"
                        placeholder={apSettings?.vcru_has_password ? '••••••••' : 'Пароль'}
                        value={apSettingsDraft.vcru_password ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_password: e.target.value }))}
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="management-form-row">
                      <label>Subsite ID (необязательно)</label>
                      <input
                        type="text"
                        placeholder="ID раздела/субсайта"
                        value={apSettingsDraft.vcru_subsite_id ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_subsite_id: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="ap-platform-block">
                    <h4>Яндекс Дзен (dzen.ru)</h4>
                    <div className="management-form-row">
                      <label className="management-checkbox">
                        <input
                          type="checkbox"
                          checked={apSettingsDraft.zen_enabled ?? false}
                          onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_enabled: e.target.checked }))}
                        />
                        Включить Яндекс Дзен
                      </label>
                    </div>
                    <div className="management-form-row">
                      <label>
                        Логин Яндекс
                      </label>
                      <input
                        type="text"
                        placeholder="login@yandex.ru"
                        value={apSettingsDraft.zen_login ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_login: e.target.value }))}
                      />
                    </div>
                    <div className="management-form-row">
                      <label>
                        Пароль Яндекс
                        {apSettings?.zen_has_password && (
                          <span className="ap-hint"> (уже задан, оставьте пустым чтобы не менять)</span>
                        )}
                      </label>
                      <input
                        type="password"
                        placeholder={apSettings?.zen_has_password ? '••••••••' : 'Пароль Яндекс'}
                        value={apSettingsDraft.zen_password ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_password: e.target.value }))}
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="management-form-row">
                      <label>Channel ID (необязательно)</label>
                      <input
                        type="text"
                        placeholder="ID вашего канала"
                        value={apSettingsDraft.zen_channel_id ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_channel_id: e.target.value }))}
                      />
                    </div>
                  </div>
                </section>

                <section className="ap-section">
                  <h3>Контент и правило 60/40</h3>
                  <div className="management-form-row">
                    <label>Процент постов с рекламой RSD AI ({apSettingsDraft.promo_ratio ?? 60}%)</label>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={5}
                      value={apSettingsDraft.promo_ratio ?? 60}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, promo_ratio: Number(e.target.value) }))}
                    />
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={apSettingsDraft.promo_ratio ?? 60}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        const safe = Number.isNaN(next) ? 60 : Math.max(0, Math.min(100, next));
                        setApSettingsDraft((p) => ({ ...p, promo_ratio: safe }));
                      }}
                    />
                    <div className="ap-ratio-labels">
                      <span>Реклама RSD AI: {apSettingsDraft.promo_ratio ?? 60}%</span>
                      <span>Нейтральные: {100 - (apSettingsDraft.promo_ratio ?? 60)}%</span>
                    </div>
                  </div>
                  <div className="management-form-row">
                    <label>Название компании</label>
                    <input
                      type="text"
                      value={apSettingsDraft.company_name ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, company_name: e.target.value }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>URL сайта</label>
                    <input
                      type="url"
                      placeholder="https://rsd.ai"
                      value={apSettingsDraft.company_url ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, company_url: e.target.value }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>Описание компании (для промо-постов)</label>
                    <textarea
                      rows={3}
                      placeholder="Кратко опишите ваш сервис..."
                      value={apSettingsDraft.company_description ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, company_description: e.target.value }))}
                    />
                  </div>
                </section>

                <section className="ap-section">
                  <h3>Темы и генерация контента</h3>
                  <div className="management-form-row">
                    <label className="management-checkbox">
                      <input
                        type="checkbox"
                        checked={apSettingsDraft.auto_topics_enabled ?? true}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, auto_topics_enabled: e.target.checked }))}
                      />
                      Автоматическая генерация тем (веб-поиск)
                    </label>
                  </div>
                  <div className="management-form-row">
                    <label>Категории тем (через запятую)</label>
                    <input
                      type="text"
                      placeholder="ИИ, IT, Автоматизация, Нейросети"
                      value={apSettingsDraft.topic_categories ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, topic_categories: e.target.value }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>Минимальная длина статьи (слов)</label>
                    <input
                      type="number"
                      min={100}
                      max={5000}
                      value={apSettingsDraft.article_min_words ?? 600}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, article_min_words: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>Максимальная длина статьи (слов)</label>
                    <input
                      type="number"
                      min={200}
                      max={10000}
                      value={apSettingsDraft.article_max_words ?? 1500}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, article_max_words: Number(e.target.value) }))}
                    />
                  </div>
                </section>

                <button
                  type="submit"
                  className="btn btn-black"
                  disabled={apIsSavingSettings}
                >
                  {apIsSavingSettings ? 'Сохранение...' : 'Сохранить настройки'}
                </button>
              </form>
            )}
          </div>
        )}

        {/* TOPICS TAB */}
        {apTab === 'topics' && (
          <div className="ap-panel">
            <div className="management-content-head">
              <span>Всего тем: {apTopicsTotal}</span>
              <button
                type="button"
                className="btn btn-outline"
                disabled={apActionInProgress === 'gen-topics' || apIsLoadingTopics}
                onClick={handleApGenerateTopics}
              >
                {apActionInProgress === 'gen-topics' ? 'Генерация...' : 'Сгенерировать темы (веб)'}
              </button>
            </div>

            <form onSubmit={handleApAddTopics} className="ap-topics-form">
              <div className="management-form-row">
                <label htmlFor="ap-topics-input">Добавить темы вручную (каждая с новой строки)</label>
                <textarea
                  id="ap-topics-input"
                  rows={5}
                  placeholder={'Как ИИ меняет рынок труда\nТоп-5 нейросетей для бизнеса\n...'}
                  value={apNewTopicsText}
                  onChange={(e) => setApNewTopicsText(e.target.value)}
                />
              </div>
              <button
                type="submit"
                className="btn btn-black"
                disabled={apActionInProgress === 'add-topics' || !apNewTopicsText.trim()}
              >
                {apActionInProgress === 'add-topics' ? 'Добавление...' : 'Добавить темы'}
              </button>
            </form>

            {apIsLoadingTopics ? (
              <p>Загрузка тем...</p>
            ) : (
              <div className="management-table-wrap">
                <table className="management-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Тема</th>
                      <th>Источник</th>
                      <th>Статус</th>
                      <th>Дата</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {apTopics.map((t) => (
                      <tr key={t.id} className={t.used ? 'ap-row-used' : ''}>
                        <td>{t.id}</td>
                        <td>{t.topic}</td>
                        <td>{t.source === 'auto' ? 'Авто' : 'Ручная'}</td>
                        <td>{t.used ? 'Использована' : 'Свободна'}</td>
                        <td>{t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            disabled={apActionInProgress === `del-topic-${t.id}`}
                            onClick={() => handleApDeleteTopic(t.id)}
                          >
                            {apActionInProgress === `del-topic-${t.id}` ? '...' : 'Удалить'}
                          </button>
                        </td>
                      </tr>
                    ))}
                    {apTopics.length === 0 && (
                      <tr><td colSpan={6}>Тем пока нет. Добавьте вручную или сгенерируйте.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* IMAGES TAB */}
        {apTab === 'images' && (
          <div className="ap-panel">
            <div className="management-content-head">
              <span>Изображений: {apImages.length}</span>
              <label className="btn btn-black ap-upload-btn" htmlFor="ap-image-upload">
                {apActionInProgress === 'upload-images' ? 'Загрузка...' : '+ Загрузить'}
                <input
                  id="ap-image-upload"
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  style={{ display: 'none' }}
                  onChange={handleApUploadImages}
                  disabled={apActionInProgress === 'upload-images'}
                />
              </label>
            </div>

            {apIsLoadingImages ? (
              <p>Загрузка изображений...</p>
            ) : (
              <div className="ap-images-grid">
                {apImages.map((img) => (
                  <div key={img.id} className="ap-image-card">
                    <img
                      src={`${ENV_CONFIG.API.BASE_URL}${img.url}`}
                      alt={img.original_name}
                      className="ap-image-thumb"
                      loading="lazy"
                    />
                    <div className="ap-image-info">
                      <span className="ap-image-name" title={img.original_name}>
                        {img.original_name.length > 20
                          ? `${img.original_name.slice(0, 18)}…`
                          : img.original_name}
                      </span>
                      <span className="ap-image-size">
                        {img.size_bytes > 1024 * 1024
                          ? `${(img.size_bytes / 1024 / 1024).toFixed(1)} МБ`
                          : `${(img.size_bytes / 1024).toFixed(0)} КБ`}
                      </span>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        disabled={apActionInProgress === `del-img-${img.id}`}
                        onClick={() => handleApDeleteImage(img.id)}
                      >
                        {apActionInProgress === `del-img-${img.id}` ? '...' : 'Удалить'}
                      </button>
                    </div>
                  </div>
                ))}
                {apImages.length === 0 && (
                  <p>Изображений нет. Загрузите PNG/JPG/WEBP для вставки в статьи.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* JOBS TAB */}
        {apTab === 'jobs' && (
          <div className="ap-panel">
            <div className="management-content-head">
              <span>Всего задач: {apJobsTotal}</span>
              <button
                type="button"
                className="btn btn-outline"
                disabled={apIsLoadingJobs}
                onClick={async () => {
                  try {
                    setApIsLoadingJobs(true);
                    const data = await adminService.apGetJobs(adminToken);
                    setApJobs(data.items ?? []);
                    setApJobsTotal(data.total ?? 0);
                  } catch (err) {
                    setApError(formatError(err));
                  } finally {
                    setApIsLoadingJobs(false);
                  }
                }}
              >
                Обновить
              </button>
            </div>
            {apIsLoadingJobs ? (
              <p>Загрузка истории...</p>
            ) : (
              <div className="management-table-wrap">
                <table className="management-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Статус</th>
                      <th>Платформа</th>
                      <th>Тема</th>
                      <th>Тип</th>
                      <th>Дата</th>
                      <th>Ссылка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apJobs.map((job) => (
                      <tr key={job.id}>
                        <td>{job.id}</td>
                        <td>
                          <span className={`management-badge ${statusClass(job.status)}`}>
                            {statusLabel(job.status)}
                          </span>
                        </td>
                        <td>{job.platform === 'vcru' ? 'vc.ru' : 'Яндекс Дзен'}</td>
                        <td title={job.topic}>
                          {job.topic.length > 50 ? `${job.topic.slice(0, 48)}…` : job.topic}
                        </td>
                        <td>
                          <span className={job.is_promo ? 'ap-badge-promo' : 'ap-badge-neutral'}>
                            {job.is_promo ? 'Промо' : 'Нейтральный'}
                          </span>
                        </td>
                        <td>
                          {job.created_at
                            ? new Date(job.created_at).toLocaleString('ru-RU')
                            : '-'}
                        </td>
                        <td>
                          {job.published_url ? (
                            <a href={job.published_url} target="_blank" rel="noopener noreferrer">
                              Открыть
                            </a>
                          ) : job.last_error ? (
                            <span className="ap-error-hint" title={job.last_error}>Ошибка</span>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                    {apJobs.length === 0 && (
                      <tr><td colSpan={7}>Задач пока нет</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* RUN / PREVIEW TAB */}
        {apTab === 'run' && (
          <div className="ap-panel">
            <section className="ap-section">
              <h3>Запустить публикацию сейчас</h3>
              <form onSubmit={handleApRunNow} className="ap-run-form">
                <div className="management-form-row">
                  <label>Платформа</label>
                  <select
                    value={apRunNowPlatform}
                    onChange={(e) => setApRunNowPlatform(e.target.value)}
                  >
                    <option value="">Авто (по настройкам)</option>
                    <option value="vcru">vc.ru</option>
                    <option value="yandex_zen">Яндекс Дзен</option>
                  </select>
                </div>
                <div className="management-form-row">
                  <label>Тема (необязательно)</label>
                  <input
                    type="text"
                    placeholder="Оставьте пустым для автовыбора из пула"
                    value={apRunNowTopic}
                    onChange={(e) => setApRunNowTopic(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-black"
                  disabled={apActionInProgress === 'run-now'}
                >
                  {apActionInProgress === 'run-now' ? 'Запуск...' : 'Опубликовать сейчас'}
                </button>
              </form>
            </section>

            <section className="ap-section">
              <h3>Предпросмотр статьи</h3>
              <form onSubmit={handleApPreview} className="ap-run-form">
                <div className="management-form-row">
                  <label>Тема статьи</label>
                  <input
                    type="text"
                    placeholder="Например: Как автоматизировать бизнес с помощью ИИ"
                    value={apPreviewTopic}
                    onChange={(e) => setApPreviewTopic(e.target.value)}
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-outline"
                  disabled={apActionInProgress === 'preview' || !apPreviewTopic.trim()}
                >
                  {apActionInProgress === 'preview' ? 'Генерация...' : 'Сгенерировать предпросмотр'}
                </button>
              </form>

              {apPreviewResult && (
                <div className="ap-preview-result">
                  <div className="ap-preview-header">
                    <strong>Заголовок:</strong> {apPreviewResult.title}
                    <span className={apPreviewResult.is_promo ? 'ap-badge-promo' : 'ap-badge-neutral'}>
                      {apPreviewResult.is_promo ? 'Промо' : 'Нейтральный'}
                    </span>
                  </div>
                  <div
                    className="ap-preview-content"
                    dangerouslySetInnerHTML={{ __html: apPreviewResult.content }}
                  />
                </div>
              )}
            </section>
          </div>
        )}
      </>
    );
  };

  const renderEmailBroadcast = () => (
    <>
      <div className="management-content-head">
        <h2>Email рассылка</h2>
      </div>
      {error && <div className="management-error">{error}</div>}

      <div className="management-broadcast-stack">
        <section className="management-broadcast-card">
          <h3 className="management-broadcast-card-title">Все подтверждённые пользователи</h3>
          <p className="management-broadcast-card-desc">
            По одному письму на адрес, с паузой между отправками (как в MailoPost). Значение паузы по умолчанию
            можно задать в окружении сервера <code>MAILOPOST_BROADCAST_INTERVAL_SECONDS</code> (например 900 = 15 мин).
          </p>
          <form className="management-broadcast-form" onSubmit={handleSendEmailBroadcast}>
            <div className="management-form-row">
              <label htmlFor="broadcast-interval">Пауза между письмами (секунд)</label>
              <input
                id="broadcast-interval"
                type="number"
                min={30}
                max={86400}
                step={1}
                value={broadcastIntervalSeconds}
                onChange={(e) => setBroadcastIntervalSeconds(Number(e.target.value))}
              />
            </div>
            <div className="management-form-row">
              <label htmlFor="broadcast-subject">Тема письма</label>
              <input
                id="broadcast-subject"
                type="text"
                maxLength={200}
                placeholder="Например: Важное обновление RSD"
                value={broadcastDraft.subject}
                onChange={(e) => setBroadcastDraft((prev) => ({ ...prev, subject: e.target.value }))}
              />
            </div>

            <div className="management-form-row">
              <label htmlFor="broadcast-body">Текст письма</label>
              <textarea
                id="broadcast-body"
                rows={10}
                maxLength={15000}
                placeholder="Введите текст рассылки. HTML-оформление будет применено автоматически."
                value={broadcastDraft.body}
                onChange={(e) => setBroadcastDraft((prev) => ({ ...prev, body: e.target.value }))}
              />
            </div>

            <div className="management-broadcast-actions">
              <button
                type="submit"
                className="btn btn-black"
                disabled={actionInProgress === 'email-broadcast' || actionInProgress === 'email-targeted'}
              >
                {actionInProgress === 'email-broadcast' ? 'Постановка в очередь...' : 'Запустить рассылку'}
              </button>
            </div>
          </form>
          {broadcastJobStatus && (
            <div
              className={`management-broadcast-result management-targeted-job ${
                broadcastJobStatus.status === 'failed' ? 'is-error' : ''
              }`}
            >
              <strong>Статус рассылки (все подтверждённые):</strong>
              <span>{broadcastJobStatus.status}</span>
              <span>
                {broadcastJobStatus.sent ?? 0} / {broadcastJobStatus.total ?? 0} отправлено
              </span>
              <span>ошибок: {broadcastJobStatus.failed ?? 0}</span>
              {broadcastJobStatus.status === 'running' && broadcastJobStatus.last_recipient && (
                <span className="management-cell-muted">
                  текущий: {broadcastJobStatus.last_recipient}
                </span>
              )}
              {broadcastJobStatus.error && (
                <span className="management-targeted-job-error">{broadcastJobStatus.error}</span>
              )}
            </div>
          )}
        </section>

        <section className="management-broadcast-card management-targeted-card">
          <h3 className="management-broadcast-card-title">Точечная рассылка по группам</h3>
          <p className="management-broadcast-card-desc">
            Создайте группы и вставьте списки email (через запятую, с новой строки, из Excel). Адреса будут
            извлечены и приведены к одному формату. Отправка через API MailoPost (
            <a href="https://mailopost.ru/api.html" target="_blank" rel="noreferrer">
              документация
            </a>
            ) — по одному письму с настраиваемой паузой, чтобы снизить риск лимитов.
          </p>

          <form className="management-targeted-groups" onSubmit={(e) => e.preventDefault()}>
            {targetedGroups.map((g) => (
              <div key={g.id} className="management-targeted-group-row">
                <label className="management-targeted-group-check">
                  <input
                    type="checkbox"
                    checked={g.selected}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setTargetedGroups((prev) =>
                        prev.map((row) => (row.id === g.id ? { ...row, selected: checked } : row))
                      );
                    }}
                  />
                  <span>Включить в рассылку</span>
                </label>
                <div className="management-form-row">
                  <label>Название группы</label>
                  <input
                    type="text"
                    maxLength={120}
                    value={g.title}
                    onChange={(e) => {
                      const v = e.target.value;
                      setTargetedGroups((prev) =>
                        prev.map((row) => (row.id === g.id ? { ...row, title: v } : row))
                      );
                    }}
                    placeholder="Например: Партнёры Q2"
                  />
                </div>
                <div className="management-form-row">
                  <label>Список email</label>
                  <textarea
                    rows={5}
                    className="management-targeted-emails-input"
                    value={g.emailsRaw}
                    onChange={(e) => {
                      const v = e.target.value;
                      setTargetedGroups((prev) =>
                        prev.map((row) => (row.id === g.id ? { ...row, emailsRaw: v } : row))
                      );
                    }}
                    placeholder={'Один адрес на строку или через запятую:\nuser@mail.ru, other@company.org'}
                  />
                </div>
                {targetedGroups.length > 1 && (
                  <button
                    type="button"
                    className="btn btn-outline management-targeted-remove"
                    onClick={() => removeTargetedGroup(g.id)}
                  >
                    Удалить группу
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="btn btn-outline" onClick={addTargetedGroup}>
              + Добавить группу
            </button>
          </form>

          <form className="management-broadcast-form management-targeted-message" onSubmit={handleTargetedSend}>
            <div className="management-form-row">
              <label>Пауза между письмами (секунд)</label>
              <input
                type="number"
                min={30}
                max={86400}
                step={1}
                value={targetedIntervalSeconds}
                onChange={(e) => setTargetedIntervalSeconds(Number(e.target.value))}
              />
              <span className="management-broadcast-hint">
                По умолчанию 900 с (15 мин). Минимум 30 с, максимум сутки.
              </span>
            </div>
            <div className="management-form-row">
              <label htmlFor="targeted-subject">Тема письма</label>
              <input
                id="targeted-subject"
                type="text"
                maxLength={200}
                value={targetedBroadcastDraft.subject}
                onChange={(e) =>
                  setTargetedBroadcastDraft((prev) => ({ ...prev, subject: e.target.value }))
                }
              />
            </div>
            <div className="management-form-row">
              <label htmlFor="targeted-body">Текст письма</label>
              <textarea
                id="targeted-body"
                rows={8}
                maxLength={15000}
                value={targetedBroadcastDraft.body}
                onChange={(e) =>
                  setTargetedBroadcastDraft((prev) => ({ ...prev, body: e.target.value }))
                }
                placeholder="Текст точечной рассылки (как для общей рассылки — простой текст, оформление в письме)."
              />
            </div>
            <div className="management-broadcast-actions management-targeted-actions">
              <button
                type="button"
                className="btn btn-outline"
                disabled={targetedPreviewLoading || actionInProgress === 'email-targeted'}
                onClick={handleTargetedPreview}
              >
                {targetedPreviewLoading ? 'Разбор списков...' : 'Проверить списки'}
              </button>
              <button
                type="submit"
                className="btn btn-black"
                disabled={actionInProgress === 'email-targeted' || actionInProgress === 'email-broadcast'}
              >
                {actionInProgress === 'email-targeted' ? 'Постановка в очередь...' : 'Запустить точечную рассылку'}
              </button>
            </div>
          </form>

          {targetedPreview && (
            <div className="management-targeted-preview">
              <strong>Разбор адресов:</strong>
              <span> уникальных получателей: {targetedPreview.unique_total ?? 0}</span>
              {targetedPreview.recipient_preview?.length > 0 && (
                <div className="management-targeted-preview-emails">
                  Примеры: {targetedPreview.recipient_preview.join(', ')}
                  {(targetedPreview.unique_total || 0) > targetedPreview.recipient_preview.length ? '…' : ''}
                </div>
              )}
              {targetedPreview.per_group && (
                <ul className="management-targeted-per-group">
                  {Object.entries(targetedPreview.per_group).map(([title, info]) => (
                    <li key={title}>
                      <strong>{title}</strong>: в группе {info.parsed_in_group}, в кампанию добавлено{' '}
                      {info.new_unique_for_campaign}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {targetedJobStatus && (
            <div
              className={`management-broadcast-result management-targeted-job ${
                targetedJobStatus.status === 'failed' ? 'is-error' : ''
              }`}
            >
              <strong>Статус точечной рассылки:</strong>
              <span>{targetedJobStatus.status}</span>
              <span>
                {targetedJobStatus.sent ?? 0} / {targetedJobStatus.total ?? 0} отправлено
              </span>
              <span>ошибок: {targetedJobStatus.failed ?? 0}</span>
              {targetedJobStatus.status === 'running' && targetedJobStatus.last_recipient && (
                <span className="management-cell-muted">текущий: {targetedJobStatus.last_recipient}</span>
              )}
              {targetedJobStatus.error && (
                <span className="management-targeted-job-error">{targetedJobStatus.error}</span>
              )}
            </div>
          )}
        </section>
      </div>
    </>
  );

  if (salesToken && !adminToken) {
    return (
      <div className="management-page">
        <header className="management-header">
          <h1>Отдел продаж</h1>
        </header>
        <main className="management-dashboard">
          <aside className="management-sidebar">
            <h3>Меню</h3>
            <nav>
              <button
                type="button"
                className={`management-menu-item ${salesSection === 'desk' ? 'active' : ''}`}
                onClick={() => setSalesSection('desk')}
              >
                Рабочий стол
              </button>
              {salesMe?.member?.role === 'rop' && (
                <button
                  type="button"
                  className={`management-menu-item ${salesSection === 'team' ? 'active' : ''}`}
                  onClick={() => setSalesSection('team')}
                >
                  Команда
                </button>
              )}
            </nav>
            <button type="button" className="btn btn-outline management-logout" onClick={handleSalesLogout}>
              Выйти
            </button>
          </aside>
          <section className="management-content">
            {salesSection === 'desk' ? renderSalesStaffDesk() : renderSalesStaffTeam()}
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="management-page">
      <header className="management-header">
        <h1>Админ-панель</h1>
      </header>

      {!adminToken ? (
        <main className="management-login-wrap">
          <div className="management-login-tabs">
            <button
              type="button"
              className={`management-login-tab ${loginPortal === 'admin' ? 'active' : ''}`}
              onClick={() => { setLoginPortal('admin'); setError(''); }}
            >
              Администратор
            </button>
            <button
              type="button"
              className={`management-login-tab ${loginPortal === 'sales' ? 'active' : ''}`}
              onClick={() => { setLoginPortal('sales'); setError(''); }}
            >
              Отдел продаж
            </button>
          </div>
          {loginPortal === 'admin' ? (
            <form className="management-login-card" onSubmit={handleLogin}>
              <h2>Вход для администратора</h2>

              <label htmlFor="admin-login">Логин</label>
              <input
                id="admin-login"
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                autoComplete="username"
                disabled={isSubmitting}
              />

              <label htmlFor="admin-password">Пароль</label>
              <input
                id="admin-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={isSubmitting}
              />

              {error && <div className="management-error">{error}</div>}

              <button type="submit" className="btn btn-black management-login-btn" disabled={isSubmitting}>
                {isSubmitting ? 'Проверка...' : 'Войти'}
              </button>
            </form>
          ) : (
            <form className="management-login-card" onSubmit={handleSalesLogin}>
              <h2>Вход для отдела продаж</h2>
              <p className="management-cell-muted">
                Стажёр, МОП или РОП — те же логин и пароль, что выдал администратор или РОП.
              </p>

              <label htmlFor="sales-login">Логин</label>
              <input
                id="sales-login"
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                autoComplete="username"
                disabled={isSubmitting}
              />

              <label htmlFor="sales-password">Пароль</label>
              <input
                id="sales-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={isSubmitting}
              />

              {error && <div className="management-error">{error}</div>}

              <button type="submit" className="btn btn-black management-login-btn" disabled={isSubmitting}>
                {isSubmitting ? 'Проверка...' : 'Войти'}
              </button>
            </form>
          )}
        </main>
      ) : (
        <main className="management-dashboard">
          <aside className="management-sidebar">
            <h3>Меню</h3>
            <nav>
              {MENU_ITEMS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`management-menu-item ${activeSection === item.id ? 'active' : ''}`}
                  onClick={() => setActiveSection(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            <button type="button" className="btn btn-outline management-logout" onClick={handleLogout}>
              Выйти
            </button>
          </aside>

          <section className="management-content">
            {activeSection === 'overview' && renderOverview()}
            {activeSection === 'users' && renderUsers()}
            {activeSection === 'agents' && renderAgents()}
            {activeSection === 'chats' && renderChats()}
            {activeSection === 'turnkeyRequests' && renderTurnkeyRequests()}
            {activeSection === 'errorReports' && renderErrorReports()}
            {activeSection === 'billing' && renderBilling()}
            {activeSection === 'promoCodes' && renderPromoCodes()}
            {activeSection === 'emailBroadcast' && renderEmailBroadcast()}
            {activeSection === 'salesDepartment' && renderSalesDepartment()}
          </section>
        </main>
      )}
    </div>
  );
};

export default ManagementPortal;
