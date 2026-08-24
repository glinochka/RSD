import React, { useState } from 'react';
import customService from '../../../services/customService';

const ACCOUNT_CLASSES = [
  { value: '', label: 'Все классы' },
  { value: 'one_day', label: 'Однодневный' },
  { value: 'mid', label: 'Средний' },
  { value: 'trusted', label: 'Доверенный' },
];

const STATUSES = [
  { value: '', label: 'Любой статус' },
  { value: 'loaded', label: 'Загружено' },
  { value: 'empty', label: 'Пусто' },
];

const CustomBulkProfileForm = ({ automationId, onSuccess }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [form, setForm] = useState({
    accountClass: '',
    status: 'loaded',
    bioTemplate: '',
    generateUnique: false,
  });
  const [avatar, setAvatar] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage(null);
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await customService.bulkUpdateProfiles(automationId, {
        avatar,
        accountClass: form.accountClass || undefined,
        status: form.status || undefined,
        bioTemplate: form.bioTemplate,
        generateUnique: form.generateUnique,
      });
      setMessage(`В очереди на обновление профилей: ${result.queued}`);
      setAvatar(null);
      setForm((f) => ({ ...f, bioTemplate: '', generateUnique: false }));
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      setError(err.message || 'Update failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setAvatar(file || null);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="text-sm text-blue-600 hover:underline"
      >
        Массовое обновление профилей
      </button>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-medium">Массовое обновление профилей</h2>
        <button
          onClick={() => setIsOpen(false)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Скрыть
        </button>
      </div>

      {message && <div className="text-green-600 text-sm">{message}</div>}
      {error && <div className="text-red-600 text-sm">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Класс</label>
            <select
              value={form.accountClass}
              onChange={(e) => setForm((f) => ({ ...f, accountClass: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            >
              {ACCOUNT_CLASSES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
            <select
              value={form.status}
              onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            >
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Шаблон bio (переменные: {'{username}'}, {'{phone_number}'}, {'{display_name}'}, {'{account_class}'})
          </label>
          <textarea
            value={form.bioTemplate}
            onChange={(e) => setForm((f) => ({ ...f, bioTemplate: e.target.value }))}
            rows={3}
            placeholder="Например: Привет, я {display_name}"
            className="w-full border border-gray-300 rounded px-3 py-2"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            id="generateUnique"
            type="checkbox"
            checked={form.generateUnique}
            onChange={(e) => setForm((f) => ({ ...f, generateUnique: e.target.checked }))}
            className="h-4 w-4"
          />
          <label htmlFor="generateUnique" className="text-sm text-gray-700">
            Генерировать уникальные bio через LLM (игнорирует шаблон)
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Аватар</label>
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="block w-full text-sm text-gray-500"
          />
          {avatar && <div className="text-xs text-gray-500 mt-1">{avatar.name}</div>}
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={isSubmitting}
            className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
          >
            {isSubmitting ? 'Отправка...' : 'Обновить профили'}
          </button>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
          >
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
};

export default CustomBulkProfileForm;
