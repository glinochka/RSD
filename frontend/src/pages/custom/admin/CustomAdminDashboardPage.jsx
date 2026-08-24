import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

const CustomAdminDashboardPage = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    customService
      .getAdminDashboard()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  const statCard = (label, value, color = 'bg-white') => (
    <div className={`${color} rounded-lg shadow p-4 text-center`}>
      <div className="text-3xl font-semibold">{value}</div>
      <div className="text-sm text-gray-500">{label}</div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Custom Admin Dashboard</h1>
        <Link
          to={NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATIONS}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
        >
          Управление автоматизациями
        </Link>
      </div>

      {error && <div className="text-red-600">{error}</div>}

      {!data ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {statCard('Автоматизации', data.total_automations)}
            {statCard('Аккаунты', data.total_accounts)}
            {statCard('Забанены', data.total_banned_accounts, 'bg-red-50')}
            {statCard('Лиды', data.total_leads, 'bg-blue-50')}
            {statCard('Сообщений', data.total_messages, 'bg-green-50')}
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="font-medium mb-4">Автоматизации</h2>
            {data.automations?.length === 0 ? (
              <div className="text-gray-500 text-center py-6">Автоматизаций пока нет.</div>
            ) : (
              <table className="w-full text-left">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">ID</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Название</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Клиент</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Аккаунты</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Лиды</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Сообщения</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Модули</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Создана</th>
                  </tr>
                </thead>
                <tbody>
                  {data.automations.map((item) => (
                    <tr key={item.id} className="border-b last:border-b-0 hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono">{item.id}</td>
                      <td className="px-4 py-3 text-sm">
                        <Link
                          to={NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATION_EDIT(item.id)}
                          className="text-blue-600 hover:underline"
                        >
                          {item.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-sm">{item.client_name || '-'}</td>
                      <td className="px-4 py-3 text-sm">
                        {item.accounts_total}
                        {item.accounts_banned > 0 && (
                          <span className="text-red-600 ml-1">({item.accounts_banned} бан)</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">{item.leads_total}</td>
                      <td className="px-4 py-3 text-sm">{item.messages_total}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex flex-wrap gap-1">
                          {item.is_dmp_one_enabled && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">DMP</span>}
                          {item.is_amocrm_enabled && <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">AmoCRM</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(item.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default CustomAdminDashboardPage;
