import React, { useState } from 'react';
import CustomSelect from '../../../components/CustomSelect';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';

const ACCOUNT_CLASSES = [
  { value: '', label: 'Все классы' },
  { value: 'one_day', label: 'Однодневный' },
  { value: 'mid', label: 'Средний' },
  { value: 'trusted', label: 'Доверенный' },
  { value: 'shilling', label: 'Шиллинг' },
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
      <button type="button" onClick={() => setIsOpen(true)} className="btn btn-outline">
        Массовое обновление профилей
      </button>
    );
  }

  return (
    <div className="settings-section">
      <div className="crm-item-header">
        <h3 className="crm-item-title">Массовое обновление профилей</h3>
        <button type="button" onClick={() => setIsOpen(false)} className="btn btn-outline">
          Скрыть
        </button>
      </div>

      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="bulk-class">Класс</label>
          <CustomSelect
            id="bulk-class"
            value={form.accountClass}
            options={ACCOUNT_CLASSES}
            onChange={(e) => setForm((f) => ({ ...f, accountClass: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="bulk-status">Статус</label>
          <CustomSelect
            id="bulk-status"
            value={form.status}
            options={STATUSES}
            onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="bulk-bio">
            Шаблон bio (переменные: {'{username}'}, {'{phone_number}'}, {'{display_name}'}, {'{account_class}'})
          </label>
          <textarea
            id="bulk-bio"
            value={form.bioTemplate}
            onChange={(e) => setForm((f) => ({ ...f, bioTemplate: e.target.value }))}
            rows={3}
            placeholder="Например: Привет, я {display_name}"
          />
        </div>
        <div className="form-group">
          <FeatureToggle
            title="Уникальные bio"
            checked={form.generateUnique}
            onChange={(checked) => setForm((f) => ({ ...f, generateUnique: checked }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="bulk-avatar">Аватар</label>
          <input id="bulk-avatar" type="file" accept="image/*" onChange={handleFileChange} />
          {avatar ? <span className="form-hint">{avatar.name}</span> : null}
        </div>
        <div className="settings-actions">
          <button type="submit" disabled={isSubmitting} className="btn btn-black">
            {isSubmitting ? 'Отправка...' : 'Обновить профили'}
          </button>
          <button type="button" onClick={() => setIsOpen(false)} className="btn btn-outline">
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
};

export default CustomBulkProfileForm;
