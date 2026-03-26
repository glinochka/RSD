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
      if (activeSection !== 'users' && activeSection !== 'agents') return;

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
  ]);

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
                  <th>Регистрация</th>
                </tr>
              </thead>
              <tbody>
                {usersState.items.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>{user.name}</td>
                    <td>{user.telegram_id ?? '-'}</td>
                    <td>{user.subscription_type}</td>
                    <td>{user.registered ? new Date(user.registered).toLocaleString() : '-'}</td>
                  </tr>
                ))}
                {usersState.items.length === 0 && (
                  <tr><td colSpan={5}>Ничего не найдено</td></tr>
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
          </section>
        </main>
      )}
    </div>
  );
};

export default ManagementPortal;
