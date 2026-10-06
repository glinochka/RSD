import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';
import { SOLUTION_KIND_LABELS } from '../automation/activityLabels';
import '../../../styles/projectLayout.css';
import '../../../styles/customSolutionNav.css';

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

  const selected = automations.find((item) => item.id === selectedId)
    || dashboard?.automations?.find((item) => item.id === selectedId);
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
    <div className="project-layout ubt-layout">
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
        <div className="ubt-page">
          <div className="ubt-hero">
            <div>
              <h1>Решения</h1>
              <p>Откройте существующее решение или создайте новое.</p>
            </div>
            <button
              type="button"
              className="btn btn-black"
              onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_NEW)}
            >
              + Новое решение
            </button>
          </div>

          {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

          {isLoading ? (
            <p className="ubt-empty">Загрузка...</p>
          ) : automations.length === 0 ? (
            <div className="ubt-panel">
              <p className="ubt-empty">Пока нет решений. Создайте первое.</p>
            </div>
          ) : (
            <div className="ubt-health">
              <div className="ubt-panel">
                <div className="ubt-panel-header">
                  <h2>Список</h2>
                </div>
                <div className="ubt-pick-list">
                  {automations.map((automation) => (
                    <button
                      key={automation.id}
                      type="button"
                      className={`ubt-pick ${selectedId === automation.id ? 'is-on' : ''}`}
                      onClick={() => setSelectedId(automation.id)}
                    >
                      <strong>{automation.name}</strong>
                      <span>
                        {SOLUTION_KIND_LABELS[automation.solution_kind] || automation.client_name || 'Без клиента'}
                        {' · '}
                        {STATUS_LABELS[automation.status] || automation.status}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="ubt-panel">
                {selected ? (
                  <>
                    <div className="ubt-panel-header">
                      <div>
                        <h2>{selected.name}</h2>
                        <p>
                          {[
                            `ID ${selected.id}`,
                            selected.client_name,
                            SOLUTION_KIND_LABELS[selected.solution_kind] !== selected.client_name
                              ? SOLUTION_KIND_LABELS[selected.solution_kind]
                              : null,
                          ].filter(Boolean).join(' · ')}
                        </p>
                      </div>
                    </div>
                    <div className="ubt-health-grid ubt-health-grid--3">
                      <div className="ubt-kpi ubt-kpi--soft">
                        <strong>{selectedStats?.accounts_total ?? '—'}</strong>
                        <span>Аккаунты</span>
                      </div>
                      <div className="ubt-kpi ubt-kpi--soft">
                        <strong>{selectedStats?.leads_total ?? '—'}</strong>
                        <span>Лиды</span>
                      </div>
                      <div className="ubt-kpi ubt-kpi--soft">
                        <strong>{selectedStats?.messages_total ?? '—'}</strong>
                        <span>Сообщения</span>
                      </div>
                    </div>
                    <p className="ubt-empty">
                      {selected.is_dmp_one_enabled || selectedStats?.is_dmp_one_enabled ? 'DMP.one · ' : ''}
                      {selected.is_amocrm_enabled || selectedStats?.is_amocrm_enabled ? 'AmoCRM' : 'Без AmoCRM'}
                    </p>
                    <div className="settings-actions">
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(selected.id))}
                      >
                        Открыть решение
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline"
                        onClick={() => handleDelete(selected.id)}
                      >
                        Удалить
                      </button>
                    </div>
                  </>
                ) : (
                  <p className="ubt-empty">Выберите решение для управления</p>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default CustomSolutionsListPage;
