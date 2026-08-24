import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';

const ROTATION_STRATEGIES = [
  { value: 'round_robin', label: 'Round Robin' },
  { value: 'least_used', label: 'Least Used' },
  { value: 'risk_weighted', label: 'Risk Weighted' },
];

const CustomAutomationSettingsPage = () => {
  const { id } = useParams();
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const loadSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
      setForm(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load settings');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleNumberChange = (e) => {
    const { name, value } = e.target;
    const parsed = parseInt(value, 10);
    setForm((prev) => ({ ...prev, [name]: Number.isNaN(parsed) ? 0 : parsed }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSuccess(null);
    setError(null);
    setIsSaving(true);
    try {
      const payload = {
        rotation_strategy: form.rotation_strategy,
        max_daily_messages_per_account: form.max_daily_messages_per_account,
        is_chat_monitoring_enabled: form.is_chat_monitoring_enabled,
        is_neurocommenting_enabled: form.is_neurocommenting_enabled,
        is_digital_footprint_enabled: form.is_digital_footprint_enabled,
        is_dmp_one_enabled: form.is_dmp_one_enabled,
        is_amocrm_enabled: form.is_amocrm_enabled,
        lead_manager_contact: form.lead_manager_contact,
        status: form.status,
      };
      const data = await customService.updateAutomationSettings(id, payload);
      setSettings(data);
      setForm(data);
      setSuccess('Настройки сохранены');
    } catch (err) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="text-gray-500">Загрузка...</div>;
  }

  if (!settings) {
    return <div className="text-red-600">{error || 'Не удалось загрузить настройки'}</div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Настройки автоматизации</h1>

      {error && <div className="text-red-600">{error}</div>}
      {success && <div className="text-green-600">{success}</div>}
      {settings?.warnings?.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 space-y-2">
          <div className="text-sm font-medium text-yellow-800">Внимание:</div>
          {settings.warnings.map((warning, idx) => (
            <div key={idx} className="text-sm text-yellow-700">{warning}</div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700">
          После сохранения с включёнными модулями автоматизация сама вступает в чаты,
          мониторит заявки, пишет комментарии, прогревает лиды и передаёт их менеджеру.
          Дальше нужно только подливать аккаунты и чаты.
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Статус воркеров</label>
          <select
            name="status"
            value={form.status || 'draft'}
            onChange={handleChange}
            className="w-full border border-gray-300 rounded px-3 py-2"
          >
            <option value="draft">Черновик (воркеры выключены)</option>
            <option value="active">Активна</option>
            <option value="paused">Пауза</option>
            <option value="archived">Архив</option>
          </select>
        </div>
        <div>
          <h2 className="font-medium mb-4">Ротация и лимиты</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Стратегия ротации</label>
              <select
                name="rotation_strategy"
                value={form.rotation_strategy || 'round_robin'}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded px-3 py-2"
              >
                {ROTATION_STRATEGIES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Ротация используется только для нейрокомментинга и массовых публичных действий, не для диалогов.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max сообщений на аккаунт в сутки
              </label>
              <input
                type="number"
                name="max_daily_messages_per_account"
                value={form.max_daily_messages_per_account || 0}
                onChange={handleNumberChange}
                min={0}
                className="w-full border border-gray-300 rounded px-3 py-2"
              />
            </div>
          </div>
        </div>

        <div>
          <h2 className="font-medium mb-4">Возможности</h2>
          <div className="space-y-3">
            {[
              { name: 'is_chat_monitoring_enabled', label: 'Мониторинг чатов' },
              { name: 'is_neurocommenting_enabled', label: 'Нейрокомментинг' },
              { name: 'is_digital_footprint_enabled', label: 'Цифровой след' },
              { name: 'is_dmp_one_enabled', label: 'DMP.one' },
              { name: 'is_amocrm_enabled', label: 'AmoCRM' },
            ].map((field) => (
              <div key={field.name} className="flex items-center gap-2">
                <input
                  id={field.name}
                  type="checkbox"
                  name={field.name}
                  checked={Boolean(form[field.name])}
                  onChange={handleChange}
                  className="h-4 w-4"
                />
                <label htmlFor={field.name} className="text-sm text-gray-700">{field.label}</label>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-3 pt-2">
            {form.is_dmp_one_enabled && (
              <Link
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP(id)}
                className="text-sm text-blue-600 hover:underline"
              >
                Перейти к DMP.one →
              </Link>
            )}
            {form.is_amocrm_enabled && (
              <Link
                to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_AMOCRM(id)}
                className="text-sm text-blue-600 hover:underline"
              >
                Перейти к AmoCRM →
              </Link>
            )}
            <Link
              to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)}
              className="text-sm text-blue-600 hover:underline"
            >
              Перейти к промптам →
            </Link>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Контакт менеджера по лидам</label>
          <input
            type="text"
            name="lead_manager_contact"
            value={form.lead_manager_contact || ''}
            onChange={handleChange}
            placeholder="Telegram / email / телефон"
            className="w-full border border-gray-300 rounded px-3 py-2"
          />
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={isSaving}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CustomAutomationSettingsPage;
