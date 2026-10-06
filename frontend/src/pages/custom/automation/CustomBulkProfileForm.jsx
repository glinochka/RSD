import React, { useState } from 'react';
import CustomSelect from '../../../components/CustomSelect';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';

const STATUSES = [
  { value: '', label: 'Любой статус' },
  { value: 'loaded', label: 'Загружено' },
  { value: 'empty', label: 'Пусто' },
];

const CustomBulkProfileForm = ({ automationId, onSuccess, embedded = false }) => {
  const [isOpen, setIsOpen] = useState(embedded);
  const [form, setForm] = useState({
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
        status: form.status || undefined,
        bioTemplate: form.bioTemplate,
        generateUnique: form.generateUnique,
        saveAsTemplate: true,
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

  const handleFileChange = (file) => {
    setAvatar(file || null);
  };

  if (!isOpen) {
    return (
      <button type="button" onClick={() => setIsOpen(true)} className="acc-btn acc-btn--ghost">
        Массовое обновление профилей
      </button>
    );
  }

  return (
    <div className={embedded ? '' : 'settings-section'}>
      {embedded ? null : (
        <div className="crm-item-header">
          <h3 className="crm-item-title">Массовое обновление профилей</h3>
          <button type="button" onClick={() => setIsOpen(false)} className="acc-btn acc-btn--ghost">
            Скрыть
          </button>
        </div>
      )}

      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}

      <form onSubmit={handleSubmit}>
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
            Шаблон bio (переменные: {'{username}'}, {'{phone_number}'}, {'{display_name}'})
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
          <CustomFileButton
            id="bulk-avatar"
            accept="image/*"
            variant="ubt"
            fileName={avatar ? avatar.name : null}
            onFile={handleFileChange}
          >
            Выбрать фото
          </CustomFileButton>
          <span className="form-hint">Шаблон сохранится для «Начать подготовку»</span>
        </div>
        <div className="settings-actions">
          <button type="submit" disabled={isSubmitting} className="acc-btn acc-btn--dark">
            {isSubmitting ? 'Отправка...' : 'Обновить профили'}
          </button>
          {embedded ? null : (
            <button type="button" onClick={() => setIsOpen(false)} className="acc-btn acc-btn--ghost">
              Отмена
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default CustomBulkProfileForm;
