import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

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

  const statCard = (label, value, color = 'bg-white') => (
    <div className={`${color} rounded-lg shadow p-4 text-center`}>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );

  const barChart = (items, total, color = 'bg-blue-500') => {
    if (!total) {
      return null;
    }
    return (
      <div className="space-y-2">
        {items.map(([key, count]) => (
          <div key={key} className="flex items-center gap-3">
            <div className="w-24 text-xs text-gray-600 truncate">{key}</div>
            <div className="flex-1 h-2 bg-gray-100 rounded overflow-hidden">
              <div
                className={`h-full ${color} rounded`}
                style={{ width: `${Math.round((count / total) * 100)}%` }}
              />
            </div>
            <div className="w-8 text-xs text-right">{count}</div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          {data && (
            <div className="text-sm text-gray-500">
              {data.client_name || data.name || `Automation #${data.automation_id}`}
            </div>
          )}
        </div>
        <div className="flex gap-3 text-sm">
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(id)} className="text-blue-600 hover:underline">
            Аккаунты
          </Link>
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)} className="text-blue-600 hover:underline">
            Чаты
          </Link>
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id)} className="text-blue-600 hover:underline">
            Лиды
          </Link>
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id)} className="text-blue-600 hover:underline">
            Настройки
          </Link>
        </div>
      </div>

      {error && <div className="text-red-600">{error}</div>}

      {!data ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {statCard('Аккаунты', data.accounts?.total)}
            {statCard('Активные', data.accounts?.active, 'bg-green-50')}
            {statCard('Забанены', data.accounts?.banned, 'bg-red-50')}
            {statCard('Лиды', data.leads?.total, 'bg-blue-50')}
            {statCard('Чатов', data.chats?.total)}
            {statCard('Вступили', data.chats?.joined, 'bg-green-50')}
            {statCard('DMP куплено', data.dmp?.purchased)}
            {statCard('Сообщений', data.actions?.total)}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-medium mb-4">Воронка лидов</h2>
              {barChart(
                STATUS_ORDER.filter((s) => (data.leads?.by_status?.[s] || 0) > 0).map((s) => [STATUS_LABELS[s] || s, data.leads.by_status[s]]),
                data.leads?.total,
                'bg-blue-500',
              )}
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-medium mb-4">Источники лидов</h2>
              {barChart(
                Object.entries(data.leads?.by_source || {}),
                data.leads?.total,
                'bg-purple-500',
              )}
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-medium mb-4">Активность за 24ч</h2>
              {barChart(
                Object.entries(data.actions?.last_24h || {}).map(([k, v]) => [ACTION_LABELS[k] || k, v]),
                Object.values(data.actions?.last_24h || {}).reduce((a, b) => a + b, 0),
                'bg-orange-500',
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-medium mb-4">Последние лиды</h2>
              {data.leads?.recent?.length === 0 ? (
                <div className="text-gray-500 text-sm">Лиды пока не появились.</div>
              ) : (
                <div className="space-y-3">
                  {data.leads.recent.map((lead) => (
                    <div key={lead.id} className="flex items-center justify-between border-b last:border-b-0 pb-2">
                      <div>
                        <div className="text-sm font-medium">{lead.contact_value}</div>
                        <div className="text-xs text-gray-500">
                          {lead.full_name || '-'} • {lead.source} • {STATUS_LABELS[lead.status] || lead.status}
                        </div>
                      </div>
                      <Link
                        to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(id, lead.id)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Чат
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-medium mb-4">Распределение аккаунтов</h2>
              {barChart(
                Object.entries(data.accounts?.by_class || {}).map(([k, v]) => [k, v]),
                data.accounts?.total,
                'bg-teal-500',
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="font-medium mb-4">Быстрые действия</h2>
            <div className="flex flex-wrap gap-3">
              <Link
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 text-sm"
              >
                Вступить в чаты
              </Link>
              <Link
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}
                className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm"
              >
                Запустить мониторинг
              </Link>
              <Link
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}
                className="bg-orange-600 text-white px-4 py-2 rounded hover:bg-orange-700 text-sm"
              >
                Нейрокомментинг
              </Link>
              <Link
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id)}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
              >
                Перейти к лидам
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default CustomAutomationDashboardPage;
