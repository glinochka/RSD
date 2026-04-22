import React, { useEffect, useMemo, useState } from 'react';
import adminService from '../services/adminService';
import { ENV_CONFIG } from '../config/environment';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/managementPortal.css';

const ADMIN_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.ADMIN_TOKEN;

const MENU_ITEMS = [
  { id: 'overview', label: 'Обзор' },
  { id: 'users', label: 'Пользователи' },
  { id: 'agents', label: 'Агенты' },
  { id: 'turnkeyRequests', label: 'Заявки под ключ' },
  { id: 'errorReports', label: 'Сообщения об ошибках' },
  { id: 'billing', label: 'Тарифы' },
  { id: 'promoCodes', label: 'Промокоды' },
];

function formatError(error) {
  return (
    error?.response?.data?.detail
    || error?.message
    || 'Не удалось выполнить запрос к админ-панели'
  );
}

const ManagementPortal = () => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [adminToken, setAdminToken] = useState(localStorage.getItem(ADMIN_TOKEN_KEY) || '');
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

  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [isSavingPlans, setIsSavingPlans] = useState(false);
  const [plansDraft, setPlansDraft] = useState([]);
  const [isLoadingPromoCodes, setIsLoadingPromoCodes] = useState(false);
  const [promoCodes, setPromoCodes] = useState([]);
  const [promoCodeDraft, setPromoCodeDraft] = useState({ code: '', discountPercent: 0 });
  const [actionInProgress, setActionInProgress] = useState(null);
  const [giftModal, setGiftModal] = useState({ open: false, user: null, planCode: 'Advanced' });

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

  const handleLogin = async (event) => {
    event.preventDefault();
    if (!login.trim() || !password) {
      setError('Введите логин и пароль администратора');
      return;
    }

    try {
      setIsSubmitting(true);
      setError('');
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

  return (
    <div className="management-page">
      <header className="management-header">
        <h1>Админ-панель</h1>
      </header>

      {!adminToken ? (
        <main className="management-login-wrap">
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
            {activeSection === 'turnkeyRequests' && renderTurnkeyRequests()}
            {activeSection === 'errorReports' && renderErrorReports()}
            {activeSection === 'billing' && renderBilling()}
            {activeSection === 'promoCodes' && renderPromoCodes()}
          </section>
        </main>
      )}
    </div>
  );
};

export default ManagementPortal;
