import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectDashboard.css';
import '../../../styles/projectCRMPage.css';

const STATUS_ORDER = ['new', 'warming', 'qualified', 'transferred', 'processing', 'converted', 'lost', 'spam'];
const STATUS_LABELS = {
  new: 'Новый',
  warming: 'Согрев',
  qualified: 'Квалифицирован',
  transferred: 'Передан',
  processing: 'В обработке',
  converted: 'Конвертирован',
  lost: 'Потерян',
  spam: 'Спам',
};

const ACTION_LABELS = {
  neurocommenting: 'Нейрокомментинг',
  discussion: 'Обсуждения',
  dm: 'ЛС',
  chat_monitoring: 'Мониторинг',
  shilling_chat: 'Шиллинг в чате',
  shilling_post: 'Шиллинг под постом',
};

const CustomAutomationDashboardPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) {
      return;
    }
    customService
      .getAutomationDashboard(id)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [id]);

  if (!data && !error) {
    return (
      <div className="project-dashboard project-dashboard--loading">
        <div className="dashboard-loading">
          <div className="dashboard-spinner" />
          <p>Загрузка дашборда...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="project-dashboard">
        <div className="dashboard-error">
          <p>{error || 'Не удалось загрузить данные'}</p>
        </div>
      </div>
    );
  }

  const funnel = STATUS_ORDER
    .map((status) => [STATUS_LABELS[status], data.leads?.by_status?.[status] || 0])
    .filter(([, count]) => count > 0);
  const actions24h = Object.entries(data.actions?.last_24h || {}).map(([key, count]) => [
    ACTION_LABELS[key] || key,
    count,
  ]);

  return (
    <div className="project-dashboard">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Дашборд</h1>
        <p className="dashboard-subtitle">
          {data.client_name || data.name || `Решение #${data.automation_id}`}
        </p>
      </div>

      <div className="dashboard-stats-grid">
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{data.actions?.total ?? 0}</span>
            <span className="dashboard-stat-label">Сообщений</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{data.leads?.total ?? 0}</span>
            <span className="dashboard-stat-label">Лидов</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{data.leads?.by_status?.transferred ?? 0}</span>
            <span className="dashboard-stat-label">Передано</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{data.accounts?.banned ?? 0}</span>
            <span className="dashboard-stat-label">Баны аккаунтов</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{data.dmp?.purchased ?? 0}</span>
            <span className="dashboard-stat-label">DMP куплено</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">
              {data.dmp?.cost_rub === undefined || data.dmp?.cost_rub === null ? '—' : `${data.dmp.cost_rub} ₽`}
            </span>
            <span className="dashboard-stat-label">Расход DMP</span>
          </div>
        </div>
      </div>

      <div className="dashboard-section">
        <div className="dashboard-section-header">
          <h2 className="dashboard-section-title">Воронка лидов</h2>
        </div>
        {funnel.length === 0 ? (
          <p className="dashboard-subtitle">Пока нет лидов.</p>
        ) : (
          <div className="dashboard-hchart dashboard-hchart--metrics">
            {funnel.map(([label, count]) => (
              <div key={label} className="dashboard-hchart-row">
                <span className="dashboard-hchart-label">{label}</span>
                <div className="dashboard-hchart-bars">
                  <div className="dashboard-hchart-bar-track dashboard-hchart-bar-track--single">
                    <div className="dashboard-hchart-bar-fill">
                      <div
                        className="dashboard-hchart-bar dashboard-hchart-bar--leads"
                        style={{ width: `${Math.round((count / (data.leads.total || 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                  <span className="dashboard-hchart-value">{count}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="dashboard-section">
        <div className="dashboard-section-header">
          <h2 className="dashboard-section-title">Активность за 24 часа</h2>
        </div>
        {actions24h.length === 0 ? (
          <p className="dashboard-subtitle">Нет действий за сутки.</p>
        ) : (
          <div className="crm-list">
            {actions24h.map(([label, count]) => (
              <div key={label} className="crm-item">
                <div className="crm-item-header">
                  <strong>{label}</strong>
                  <span>{count}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="dashboard-section">
        <div className="dashboard-section-header">
          <h2 className="dashboard-section-title">Последние диалоги</h2>
        </div>
        {!data.leads?.recent?.length ? (
          <p className="dashboard-subtitle">Диалогов пока нет.</p>
        ) : (
          <div className="crm-list">
            {data.leads.recent.map((lead) => (
              <Link
                key={lead.id}
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(id, lead.id)}
                className="crm-item"
              >
                <div className="crm-item-header">
                  <strong>{lead.contact_value || lead.full_name || `Лид #${lead.id}`}</strong>
                  <span className="crm-status">{STATUS_LABELS[lead.status] || lead.status}</span>
                </div>
                <span>{lead.source}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationDashboardPage;
