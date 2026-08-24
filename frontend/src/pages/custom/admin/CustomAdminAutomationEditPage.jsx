import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

const CustomAdminAutomationEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';

  const [form, setForm] = useState({
    name: '',
    client_name: '',
    industry: '',
    description: '',
    status: 'draft',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isNew) {
      loadAutomation(id);
    }
  }, [id, isNew]);

  const loadAutomation = async (automationId) => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomation(automationId);
      setForm({
        name: data.name || '',
        client_name: data.client_name || '',
        industry: data.industry || '',
        description: data.description || '',
        status: data.status || 'draft',
      });
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load automation');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setIsSaving(true);
      if (isNew) {
        await customService.createAutomation(form);
      } else {
        await customService.updateAutomation(id, form);
      }
      navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATIONS);
    } catch (err) {
      setError(err.message || 'Failed to save automation');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="text-gray-500">Загрузка...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold mb-6">
        {isNew ? 'Новая автоматизация' : 'Редактирование автоматизации'}
      </h1>

      {error && <div className="text-red-600 mb-4">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Название</label>
          <input
            type="text"
            name="name"
            value={form.name}
            onChange={handleChange}
            required
            className="w-full border border-gray-300 rounded px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Клиент</label>
          <input
            type="text"
            name="client_name"
            value={form.client_name}
            onChange={handleChange}
            className="w-full border border-gray-300 rounded px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Индустрия</label>
          <input
            type="text"
            name="industry"
            value={form.industry}
            onChange={handleChange}
            className="w-full border border-gray-300 rounded px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
          <textarea
            name="description"
            value={form.description}
            onChange={handleChange}
            rows={4}
            className="w-full border border-gray-300 rounded px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
          <select
            name="status"
            value={form.status || 'draft'}
            onChange={handleChange}
            className="w-full border border-gray-300 rounded px-3 py-2"
          >
            <option value="draft">Черновик</option>
            <option value="active">Активна</option>
            <option value="paused">Пауза</option>
            <option value="archived">Архив</option>
          </select>
        </div>
        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={isSaving}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
          <button
            type="button"
            onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATIONS)}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
          >
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
};

export default CustomAdminAutomationEditPage;
