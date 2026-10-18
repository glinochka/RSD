import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { useLiveRef } from './ubtPersist';
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

  const formRef = useLiveRef(form);

  const persistFlag = (partial) => {
    const next = { ...formRef.current, ...partial };
    formRef.current = next;
    setForm(next);
    setIsSaving(true);
    setSuccess(null);
    setError(null);
    const payload = {
      is_lead_qualification_enabled: Boolean(next.is_lead_qualification_enabled),
      is_sasha_ai_enabled: Boolean(next.is_sasha_ai_enabled),
      sasha_auto_push: next.sasha_auto_push !== false,
      sasha_qualify_on_commit: next.sasha_qualify_on_commit !== false,
      sasha_notify_on_commit: next.sasha_notify_on_commit !== false,
    };
    if (settings?.solution_kind === 'dmp_bot') {
      payload.is_amocrm_enabled = Boolean(next.is_amocrm_enabled);
    }
    customService.updateAutomationSettings(id, payload)
      .then((data) => {
        setSettings(data);
        setForm(data);
        setSuccess('Настройки DMP сохранены');
      })
      .catch((err) => setError(err.message || 'Не удалось сохранить'))
      .finally(() => setIsSaving(false));
  };

  const handleSave = (e) => {
    e.preventDefault();
    persistFlag({});
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
          <p>Один контур: номер из DMP либо звонит Sasha AI, либо его пишет аккаунт перехвата, либо он сразу уходит в Telegram-бот.</p>
        </div>
      </div>
      {error ? <p className="form-hint">{error}</p> : null}
      {success ? <p className="form-hint">{success}</p> : null}

      <form className="ubt-panel" onSubmit={handleSave}>
        <div className="settings-toggles">
          <FeatureToggle
            title="Квалификация номеров"
            description={form.is_sasha_ai_enabled
              ? 'Пока Sasha AI включена, номер с телефоном она забирает на прозвон. Этот тумблер остаётся для контактов без телефона и на случай, когда прозвон выключен: аккаунт из «Перехват заявок» пишет в ЛС, затем карточка уходит в бота.'
              : 'Вкл: аккаунт из «Перехват заявок» находит человека по номеру, пишет в ЛС и квалифицирует, затем карточка уходит в Telegram-бота. Выкл: номер сразу приходит в бота, без диалога.'}
            checked={Boolean(form.is_lead_qualification_enabled)}
            onChange={(checked) => persistFlag({ is_lead_qualification_enabled: checked })}
          />
          <FeatureToggle
            title="Прозвон Sasha AI"
            description="DMP отдаёт номер сюда, мы отправляем его Саше, после звонка результат возвращается сюда. Если договорились — в Telegram-бот уходит та же карточка, что у лидов из чатов. Заявки из чатов Саша не прозванивает."
            checked={Boolean(form.is_sasha_ai_enabled)}
            onChange={(checked) => persistFlag({ is_sasha_ai_enabled: checked })}
          />
          {form.is_sasha_ai_enabled ? (
            <>
              <FeatureToggle
                title="Автоматически отдавать номера Саше"
                description="Каждый новый контакт из DMP сразу попадает в колл-лист Sasha AI."
                checked={form.sasha_auto_push !== false}
                onChange={(checked) => persistFlag({ sasha_auto_push: checked })}
              />
              <FeatureToggle
                title="Квалифицировать после договорённости"
                description="Если Саша договорилась о следующем шаге, лид становится квалифицированным."
                checked={form.sasha_qualify_on_commit !== false}
                onChange={(checked) => persistFlag({ sasha_qualify_on_commit: checked })}
              />
              <FeatureToggle
                title="Присылать лид в Telegram"
                description="После договорённости бот получает ту же карточку: дата, телефон, что нужно, диалог звонка и прогрев."
                checked={form.sasha_notify_on_commit !== false}
                onChange={(checked) => persistFlag({ sasha_notify_on_commit: checked })}
              />
            </>
          ) : null}
          {settings?.solution_kind === 'dmp_bot' ? (
            <FeatureToggle
              title="Отправлять в AmoCRM"
              description="Квалифицированные номера уходят в воронку CRM."
              checked={Boolean(form.is_amocrm_enabled)}
              onChange={(checked) => persistFlag({ is_amocrm_enabled: checked })}
            />
          ) : null}
        </div>
        <p className="form-hint" style={{ marginTop: 12 }}>
          {form.is_sasha_ai_enabled
            ? 'Номер с телефоном: DMP → Sasha AI → этот сервис → Telegram-бот. Контакт без телефона идёт по тумблеру квалификации.'
            : form.is_lead_qualification_enabled
              ? 'Номер: DMP → аккаунт из перехвата пишет в ЛС → Telegram-бот.'
              : 'Номер: DMP → сразу Telegram-бот, без звонка и без диалога.'}
          {' '}
          Заявки из чатов всегда идут через перехват и тот же бот.
        </p>
        <p className="form-hint">
          Подключение Sasha AI — на странице
          {' '}
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_CONNECTION(id)}>Подключение</Link>
          .
          {' '}
          {settings?.solution_kind === 'dmp_bot'
            ? 'Telegram-аккаунт для квалификации берётся из пула решения.'
            : (
              <>
                Telegram-аккаунт для квалификации — тот же, что выбран в
                {' '}
                <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_UBT(id, 'lead-intercept')}>Перехвате заявок</Link>
                .
              </>
            )}
          {' '}
          Бот и таблица настраиваются в
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
