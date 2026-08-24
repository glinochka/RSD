import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';
import '../../../styles/projectLayout.css';
import '../../../styles/agentsPage.css';
import '../../../styles/projectDashboard.css';

const STATUS_LABELS = {
  draft: 'Черновик',
  active: 'Активно',
  paused: 'Пауза',
  archived: 'Архив',
};

const CustomSolutionsListPage = () => {
  const navigate = useNavigate();
  const { logout } = useCustomAuth();
  const [automations, setAutomations] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([customService.listAutomations(), customService.getAdminDashboard()])
      .then(([list, stats]) => {
        if (!mounted) {
          return;
        }
        const items = list.items || [];
        setAutomations(items);
        setDashboard(stats);
        setSelectedId((prev) => prev || items[0]?.id || null);
        setError(null);
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Не удалось загрузить решения');
        }
      })
      .finally(() => {
        if (mounted) {
          setIsLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selected = automations.find((item) => item.id === selectedId) || dashboard?.automations?.find((item) => item.id === selectedId);
  const selectedStats = dashboard?.automations?.find((item) => item.id === selectedId);

  const handleDelete = async (id) => {
    if (!window.confirm('Удалить решение?')) {
      return;
    }
    try {
      await customService.deleteAutomation(id);
      const next = automations.filter((item) => item.id !== id);
      setAutomations(next);
      setSelectedId(next[0]?.id || null);
    } catch (err) {
      setError(err.message || 'Не удалось удалить');
    }
  };

  return (
    <div className="project-layout">
      <header className="project-topbar">
        <div className="project-topbar-left">
          <h1 className="project-topbar-title">Кастомные агенты</h1>
        </div>
        <div className="project-topbar-right">
          <span className="project-topbar-user">Администратор</span>
          <button type="button" className="project-topbar-back" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>

      <main className="project-content">
        <div className="agents-page-content">
          <section className="agents-section">
          <div className="section-header">
            <h2 className="section-title">Решения</h2>
            <button
              type="button"
              className="btn btn-black btn-add"
              onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_NEW)}
            >
              + Новое решение
            </button>
          </div>

          {error ? <div className="dashboard-error">{error}</div> : null}

          {isLoading ? (
            <div className="dashboard-loading">Загрузка...</div>
          ) : automations.length === 0 ? (
            <div className="agent-management-empty">Пока нет решений. Создайте первое.</div>
          ) : (
            <div className="agents-layout">
              <div className="agents-list">
                {automations.map((automation) => (
                  <div
                    key={automation.id}
                    className={`agent-item ${selectedId === automation.id ? 'agent-item--selected' : ''}`}
                    onClick={() => setSelectedId(automation.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        setSelectedId(automation.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="agent-info">
                      <span
                        className={`agent-status-dot ${
                          automation.status === 'active' ? 'agent-status-dot--active' : 'agent-status-dot--inactive'
                        }`}
                      />
                      <div className="agent-details">
                        <h3 className="agent-name">{automation.name}</h3>
                        <p className="agent-role">
                          {automation.client_name || 'Без клиента'} · {STATUS_LABELS[automation.status] || automation.status}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="agent-management-card">
                {selected ? (
                  <>
                    <div className="agent-management-header">
                      <h3>{selected.name}</h3>
                      <p>ID: {selected.id}</p>
                      <p>{selected.client_name || 'Клиент не указан'}</p>
                    </div>
                    <div className="dashboard-stats-grid">
                      <div className="dashboard-stat-card">
                        <div className="dashboard-stat-content">
                          <span className="dashboard-stat-value">{selectedStats?.accounts_total ?? '—'}</span>
                          <span className="dashboard-stat-label">Аккаунты</span>
                        </div>
                      </div>
                      <div className="dashboard-stat-card">
                        <div className="dashboard-stat-content">
                          <span className="dashboard-stat-value">{selectedStats?.leads_total ?? '—'}</span>
                          <span className="dashboard-stat-label">Лиды</span>
                        </div>
                      </div>
                      <div className="dashboard-stat-card">
                        <div className="dashboard-stat-content">
                          <span className="dashboard-stat-value">{selectedStats?.messages_total ?? '—'}</span>
                          <span className="dashboard-stat-label">Сообщения</span>
                        </div>
                      </div>
                    </div>
                    <p className="agent-role">
                      {selected.is_dmp_one_enabled || selectedStats?.is_dmp_one_enabled ? 'DMP.one · ' : ''}
                      {selected.is_amocrm_enabled || selectedStats?.is_amocrm_enabled ? 'AmoCRM' : 'Без AmoCRM'}
                    </p>
                    <button
                      type="button"
                      className="btn btn-black analytics-btn"
                      onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(selected.id))}
                    >
                      Открыть решение
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline analytics-btn"
                      onClick={() => handleDelete(selected.id)}
                    >
                      Удалить
                    </button>
                  </>
                ) : (
                  <div className="agent-management-empty">Выберите решение для управления</div>
                )}
              </div>
            </div>
          )}
          </section>
        </div>
      </main>
    </div>
  );
};

export default CustomSolutionsListPage;
