import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

const CustomAdminAutomationsPage = () => {
  const navigate = useNavigate();
  const [automations, setAutomations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAutomations = async () => {
    try {
      setIsLoading(true);
      const data = await customService.listAutomations();
      setAutomations(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load automations');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAutomations();
  }, []);

  const handleDelete = async (id) => {
    if (!window.confirm('Удалить автоматизацию?')) {
      return;
    }
    try {
      await customService.deleteAutomation(id);
      await loadAutomations();
    } catch (err) {
      setError(err.message || 'Failed to delete automation');
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Автоматизации</h1>
        <button
          onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATIONS + '/new')}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          + Создать автоматизацию
        </button>
      </div>

      {error && <div className="text-red-600 mb-4">{error}</div>}

      {isLoading ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : automations.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          Нет автоматизаций. Создайте первую.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Название</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Клиент</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Действия</th>
              </tr>
            </thead>
            <tbody>
              {automations.map((automation) => (
                <tr key={automation.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium">{automation.name}</div>
                    {automation.industry && (
                      <div className="text-xs text-gray-500">{automation.industry}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">{automation.client_name || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className="inline-flex px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">
                      {automation.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATION_EDIT(automation.id))}
                        className="text-blue-600 hover:underline"
                      >
                        Редактировать
                      </button>
                      <button
                        onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATION_ACCESS(automation.id))}
                        className="text-green-600 hover:underline"
                      >
                        Доступы
                      </button>
                      <button
                        onClick={() => handleDelete(automation.id)}
                        className="text-red-600 hover:underline"
                      >
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default CustomAdminAutomationsPage;
