import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

const CustomAdminAutomationAccessPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [automation, setAutomation] = useState(null);
  const [credentials, setCredentials] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newCredential, setNewCredential] = useState({ username: '', password: '' });

  useEffect(() => {
    loadData();
  }, [id]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [automationData, credentialsData] = await Promise.all([
        customService.getAutomation(id),
        customService.listCredentials(id),
      ]);
      setAutomation(automationData);
      setCredentials(credentialsData.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (credentialId) => {
    if (!window.confirm('Удалить доступ клиента?')) {
      return;
    }
    try {
      await customService.deleteCredential(id, credentialId);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete credential');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      setIsCreating(true);
      await customService.createCredential(id, newCredential);
      setNewCredential({ username: '', password: '' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to create credential');
    } finally {
      setIsCreating(false);
    }
  };

  if (isLoading) {
    return <div className="text-gray-500">Загрузка...</div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">
          Доступы клиента: {automation?.name || id}
        </h1>
        <button
          onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATIONS)}
          className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
        >
          К списку
        </button>
      </div>

      {error && <div className="text-red-600">{error}</div>}

      <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-4 space-y-4">
        <h2 className="font-medium">Новый доступ</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Логин</label>
            <input
              type="text"
              value={newCredential.username}
              onChange={(e) => setNewCredential((p) => ({ ...p, username: e.target.value }))}
              required
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
            <input
              type="text"
              value={newCredential.password}
              onChange={(e) => setNewCredential((p) => ({ ...p, password: e.target.value }))}
              required
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={isCreating}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isCreating ? 'Создание...' : 'Создать'}
        </button>
      </form>

      {credentials.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          Нет доступов. Создайте первый логин/пароль для клиента.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Логин</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Последний вход</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Действия</th>
              </tr>
            </thead>
            <tbody>
              {credentials.map((credential) => (
                <tr key={credential.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-sm">{credential.username}</td>
                  <td className="px-4 py-3 text-sm">
                    <span
                      className={`inline-flex px-2 py-1 rounded text-xs ${
                        credential.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {credential.is_active ? 'Активен' : 'Неактивен'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {credential.last_login_at
                      ? new Date(credential.last_login_at).toLocaleString()
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <button
                      onClick={() => handleDelete(credential.id)}
                      className="text-red-600 hover:underline"
                    >
                      Удалить
                    </button>
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

export default CustomAdminAutomationAccessPage;
