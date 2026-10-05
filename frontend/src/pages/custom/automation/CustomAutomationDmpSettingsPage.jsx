import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';

const CustomAutomationDmpSettingsPage = () => {
  const { id } = useParams();
  const [form, setForm] = useState({});
  const [settings, setSettings] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
      setForm(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить настройки DMP');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setSuccess(null);
    setError(null);
    try {
      const payload = {
        is_lead_qualification_enabled: Boolean(form.is_lead_qualification_enabled),
      };
      if (settings?.solution_kind === 'dmp_bot') {
        payload.is_amocrm_enabled = Boolean(form.is_amocrm_enabled);
      }
      const data = await customService.updateAutomationSettings(id, payload);
      setSettings(data);
      setForm(data);
      setSuccess('Настройки DMP сохранены');
    } catch (err) {
      setError(err.message || 'Не удалось сохранить');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="ubt-page">
        <p className="ubt-empty">Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Настройки DMP</h1>
          <p>Квалификация полученных номеров и передача в CRM / Telegram.</p>
        </div>
      </div>
      {error ? <p className="form-hint">{error}</p> : null}
      {success ? <p className="form-hint">{success}</p> : null}

      <form className="ubt-panel" onSubmit={handleSave}>
        <div className="settings-toggles">
          <FeatureToggle
            title="Квалификация номеров"
            description="ИИ находит чат по номеру и квалифицирует лид, прежде чем отдавать его дальше."
            checked={Boolean(form.is_lead_qualification_enabled)}
            onChange={(checked) => setForm((prev) => ({ ...prev, is_lead_qualification_enabled: checked }))}
          />
          {settings?.solution_kind === 'dmp_bot' ? (
            <FeatureToggle
              title="Отправлять в AmoCRM"
              description="Квалифицированные номера уходят в воронку CRM."
              checked={Boolean(form.is_amocrm_enabled)}
              onChange={(checked) => setForm((prev) => ({ ...prev, is_amocrm_enabled: checked }))}
            />
          ) : null}
        </div>
        <p className="form-hint" style={{ marginTop: 12 }}>
          Telegram-аккаунт для квалификации берётся из пула решения. Бот и таблица настраиваются в
          {' '}
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_INTEGRATIONS(id)}>Интеграциях</Link>
          {settings?.solution_kind === 'dmp_bot' ? '.' : (
            <>
              . Включить AmoCRM можно в
              {' '}
              <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id)}>общих настройках</Link>
              .
            </>
          )}
        </p>
        <div className="settings-actions">
          <button type="submit" className="btn btn-black" disabled={isSaving}>
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CustomAutomationDmpSettingsPage;
