import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import FeatureToggle from '../../../components/FeatureToggle';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import customService from '../../../services/customService';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import CustomAutomationIntegrationsBlock from './CustomAutomationIntegrationsBlock';
import { ACTIVITY_MODULE_TOGGLES } from './activityLabels';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

const ROTATION_STRATEGIES = [
  { value: 'round_robin', label: 'По кругу' },
  { value: 'least_used', label: 'Меньше использовался' },
  { value: 'risk_weighted', label: 'По риску бана' },
];

const CustomAutomationSettingsPage = () => {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAdmin } = useCustomAuth();
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [credentials, setCredentials] = useState([]);
  const [newCredential, setNewCredential] = useState({ username: '', password: '' });
  const [isCreatingAccess, setIsCreatingAccess] = useState(false);
  const [keywordDraft, setKeywordDraft] = useState('');

  const loadSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
      setForm(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить настройки');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const loadCredentials = useCallback(async () => {
    if (!isAdmin) {
      return;
    }
    try {
      const data = await customService.listCredentials(id);
      setCredentials(data.items || []);
    } catch (err) {
      setCredentials([]);
    }
  }, [id, isAdmin]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    loadCredentials();
  }, [loadCredentials]);

  useEffect(() => {
    const amocrm = searchParams.get('amocrm');
    if (!amocrm) {
      return;
    }
    if (amocrm === 'connected') {
      setSuccess('AmoCRM подключено');
    } else if (amocrm === 'error') {
      setError('Не удалось подключить AmoCRM');
    }
    const next = new URLSearchParams(searchParams);
    next.delete('amocrm');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const leadKeywords = Array.isArray(form.lead_keywords) ? form.lead_keywords : [];

  const addLeadKeywords = (raw) => {
    const parts = String(raw || '')
      .split(/[\n,;]+/)
      .map((part) => part.trim().toLowerCase())
      .filter((part) => part.length >= 2)
      .map((part) => part.slice(0, 64));
    if (parts.length === 0) {
      return;
    }
    setForm((prev) => {
      const current = Array.isArray(prev.lead_keywords) ? prev.lead_keywords : [];
      const next = [...current];
      parts.forEach((part) => {
        if (!next.includes(part) && next.length < 50) {
          next.push(part);
        }
      });
      return { ...prev, lead_keywords: next };
    });
    setKeywordDraft('');
  };

  const removeLeadKeyword = (word) => {
    setForm((prev) => ({
      ...prev,
      lead_keywords: (Array.isArray(prev.lead_keywords) ? prev.lead_keywords : []).filter((item) => item !== word),
    }));
  };

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
      const payload = settings.solution_kind === 'dmp_bot'
        ? {
            is_dmp_one_enabled: true,
            is_lead_qualification_enabled: Boolean(form.is_lead_qualification_enabled),
          }
        : {
            rotation_strategy: form.rotation_strategy,
            max_daily_messages_per_account: form.max_daily_messages_per_account,
            is_chat_monitoring_enabled: form.is_chat_monitoring_enabled,
            is_neurocommenting_enabled: form.is_neurocommenting_enabled,
            is_shilling_enabled: form.is_shilling_enabled,
            is_digital_footprint_enabled: form.is_digital_footprint_enabled,
            is_dmp_one_enabled: form.is_dmp_one_enabled,
            is_amocrm_enabled: form.is_amocrm_enabled,
            lead_keywords: Array.isArray(form.lead_keywords) ? form.lead_keywords : [],
            lead_manager_contact: form.lead_manager_contact,
            partner_utm_url: form.partner_utm_url,
            partner_promo_code: form.partner_promo_code,
            conversion_check_url: form.conversion_check_url,
            proxy_list_text: form.proxy_list_text || '',
            account_warmup_usernames: isAdmin
              ? (form.account_warmup_usernames || []).map((item) => String(item || '').trim()).filter(Boolean)
              : undefined,
            account_warmup_messages: isAdmin
              ? (form.account_warmup_messages || []).map((item) => String(item || '').trim()).filter(Boolean)
              : undefined,
          };
      const data = await customService.updateAutomationSettings(id, payload);
      setSettings(data);
      setForm(data);
      setSuccess('Настройки сохранены');
    } catch (err) {
      setError(err.message || 'Не удалось сохранить');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateAccess = async (e) => {
    e.preventDefault();
    setIsCreatingAccess(true);
    setError(null);
    try {
      await customService.createCredential(id, newCredential);
      setNewCredential({ username: '', password: '' });
      await loadCredentials();
    } catch (err) {
      setError(err.message || 'Не удалось создать доступ');
    } finally {
      setIsCreatingAccess(false);
    }
  };

  if (isLoading) {
    return (
      <div className="project-settings-page project-settings-page--loading">
        <div className="settings-loading">
          <div className="spinner" />
          <p>Загрузка настроек...</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="project-settings-page">
        <p>{error || 'Не удалось загрузить настройки'}</p>
      </div>
    );
  }

  return (
    <div className="project-settings-page">
      <div className="settings-header">
        <div>
          <h1 className="settings-title">Настройки</h1>
          <p className="settings-subtitle">
            {settings?.solution_kind === 'dmp_bot'
              ? 'Бот, DMP, таблица и доступ клиента.'
              : 'Модули, ротация и доступ клиента.'}
          </p>
        </div>
      </div>

      {error ? <p className="form-hint">{error}</p> : null}
      {success ? <p className="form-hint">{success}</p> : null}
      {settings?.warnings?.length > 0 ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Внимание</h3>
          {settings.warnings.map((warning) => (
            <p key={warning} className="form-hint">{warning}</p>
          ))}
        </div>
      ) : null}

      <form className="settings-form" onSubmit={handleSubmit}>
        <div className="settings-section">
          <h3 className="settings-section-title">Модули</h3>
          <div className="settings-toggles">
            {settings.solution_kind === 'dmp_bot' ? (
              <FeatureToggle
                title="Квалификация"
                description="ИИ найдёт чат по номеру и квалифицирует лид. В бот и таблицу уйдёт только квалифицированный."
                checked={Boolean(form.is_lead_qualification_enabled)}
                onChange={(checked) => setForm((prev) => ({ ...prev, is_lead_qualification_enabled: checked }))}
              />
            ) : (
              ACTIVITY_MODULE_TOGGLES.filter((field) => {
                if (field.name === 'is_amocrm_enabled' && settings.solution_kind === 'seo_saas') {
                  return false;
                }
                return true;
              }).map((field) => (
                <FeatureToggle
                  key={field.name}
                  title={field.label}
                  checked={Boolean(form[field.name])}
                  onChange={(checked) => setForm((prev) => ({ ...prev, [field.name]: checked }))}
                />
              ))
            )}
          </div>
        </div>

        {settings.solution_kind === 'dmp_bot' ? null : (
        <div className="settings-section">
          <h3 className="settings-section-title">Ключевые слова для перехвата</h3>
          <p className="form-hint">
            Сначала совпадение со словом, потом LLM. Без списка сообщения не проверяются.
          </p>
          {leadKeywords.length > 0 ? (
            <ul className="lead-keywords-list">
              {leadKeywords.map((word) => (
                <li key={word} className="lead-keyword-chip">
                  <span>{word}</span>
                  <button
                    type="button"
                    className="lead-keyword-remove"
                    onClick={() => removeLeadKeyword(word)}
                  >
                    Удалить
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="form-hint">Пока нет слов — перехват не будет тратить токены и не напишет в ЛС.</p>
          )}
          <div className="lead-keyword-add">
            <input
              id="lead_keyword_draft"
              type="text"
              value={keywordDraft}
              onChange={(e) => setKeywordDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addLeadKeywords(keywordDraft);
                }
              }}
              placeholder="seo, нужен сайт"
              maxLength={64}
              disabled={leadKeywords.length >= 50}
            />
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => addLeadKeywords(keywordDraft)}
              disabled={!keywordDraft.trim() || leadKeywords.length >= 50}
            >
              Добавить
            </button>
          </div>
        </div>
        )}

        {settings.solution_kind === 'dmp_bot' ? null : (
        <div className="settings-section">
          <h3 className="settings-section-title">Ротация</h3>
          <div className="form-group">
            <label htmlFor="rotation_strategy">Стратегия</label>
            <CustomSelect
              id="rotation_strategy"
              name="rotation_strategy"
              value={form.rotation_strategy || 'round_robin'}
              options={ROTATION_STRATEGIES}
              onChange={handleChange}
            />
          </div>
          <div className="form-group">
            <label htmlFor="max_daily_messages_per_account">Лимит сообщений на аккаунт в сутки</label>
            <input
              id="max_daily_messages_per_account"
              type="number"
              name="max_daily_messages_per_account"
              value={form.max_daily_messages_per_account || 0}
              onChange={handleNumberChange}
              min={0}
            />
          </div>
        </div>
        )}

        {settings.solution_kind === 'dmp_bot' ? null : (settings.solution_kind === 'seo_saas' || settings.is_dmp_one_enabled || settings.solution_kind === 'fulfillment') ? (
          <div className="settings-section">
            <h3 className="settings-section-title">Партнёрка</h3>
            <div className="form-group">
              <label htmlFor="partner_utm_url">Ссылка с UTM</label>
              <input
                id="partner_utm_url"
                type="text"
                name="partner_utm_url"
                value={form.partner_utm_url || ''}
                onChange={handleChange}
                placeholder="https://example.com/?utm_source=telegram"
              />
            </div>
            <div className="form-group">
              <label htmlFor="partner_promo_code">Промокод</label>
              <input
                id="partner_promo_code"
                type="text"
                name="partner_promo_code"
                value={form.partner_promo_code || ''}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="conversion_check_url">Проверка регистрации</label>
              <input
                id="conversion_check_url"
                type="text"
                name="conversion_check_url"
                value={form.conversion_check_url || ''}
                onChange={handleChange}
                placeholder="https://saas.example.com/api/lead-status"
              />
            </div>
          </div>
        ) : null}

        {settings.solution_kind === 'seo_saas' || settings.solution_kind === 'dmp_bot' ? null : (
        <div className="settings-section">
          <h3 className="settings-section-title">Передача лидов</h3>
          <div className="form-group">
            <label htmlFor="lead_manager_contact">
              {settings.solution_kind === 'fulfillment' ? 'Telegram МОПа' : 'Контакт менеджера'}
            </label>
            <input
              id="lead_manager_contact"
              type="text"
              name="lead_manager_contact"
              value={form.lead_manager_contact || ''}
              onChange={handleChange}
              placeholder={settings.solution_kind === 'fulfillment' ? '@mop_account' : 'Telegram / email / webhook'}
            />
          </div>
        </div>
        )}

        {settings.solution_kind === 'dmp_bot' ? null : (
        <div className="settings-section">
          <h3 className="settings-section-title">Прокси</h3>
          <p className="form-hint">
            Один прокси на строку. При сохранении список равномерно раздаётся по аккаунтам,
            чтобы Telegram не видел все запросы с IP сервера.
            Форматы: <code>host:port</code>, <code>host:port:user:pass</code>,{' '}
            <code>socks5://user:pass@host:port</code>.
          </p>
          {settings.proxy_count > 0 ? (
            <p className="form-hint">
              {settings.proxy_count} прокси на {settings.accounts_with_proxy || 0} аккаунтов
              {Array.isArray(settings.proxy_distribution) && settings.proxy_distribution.length
                ? ` — ${settings.proxy_distribution
                    .map((item) => `${item.host}:${item.port} (${item.account_count})`)
                    .join(', ')}`
                : ''}
              .
            </p>
          ) : (
            <p className="form-hint">Пока нет прокси — аккаунты ходят с IP VPS.</p>
          )}
          <div className="form-group">
            <label htmlFor="proxy_list_text">Список прокси</label>
            <textarea
              id="proxy_list_text"
              name="proxy_list_text"
              rows={8}
              value={form.proxy_list_text || ''}
              onChange={handleChange}
              placeholder={'1.2.3.4:1080\n5.6.7.8:1080:user:pass\nsocks5://user:pass@9.8.7.6:1080'}
            />
          </div>
          <div className="settings-actions">
            <CustomFileButton
              accept=".txt,text/plain"
              onFile={async (file) => {
                const text = await file.text();
                setForm((prev) => ({ ...prev, proxy_list_text: text }));
              }}
            >
              Загрузить .txt
            </CustomFileButton>
          </div>
        </div>
        )}

        {isAdmin && settings.solution_kind !== 'dmp_bot' ? (
          <div className="settings-section">
            <h3 className="settings-section-title">Прогрев аккаунтов</h3>
            <p className="form-hint">
              1–3 юзернейма доверенных аккаунтов, которым новые сессии пишут мини-диалог на второй и третий день.
              {form.account_warmup_enabled
                ? ' Прогрев включён — следующие заливы идут в прогрев.'
                : ' Прогрев ещё не включён: кнопка «Начать прогрев» в разделе Аккаунты.'}
            </p>
            {[0, 1, 2].map((index) => (
              <div key={`warmup-user-${index}`} className="form-group">
                <label htmlFor={`warmup-user-${index}`}>Юзернейм {index + 1}</label>
                <input
                  id={`warmup-user-${index}`}
                  type="text"
                  value={(form.account_warmup_usernames || [])[index] || ''}
                  onChange={(e) => {
                    const next = [...(form.account_warmup_usernames || [])];
                    next[index] = e.target.value;
                    setForm((prev) => ({ ...prev, account_warmup_usernames: next }));
                  }}
                  placeholder="@username"
                />
              </div>
            ))}
            {[0, 1, 2].map((index) => (
              <div key={`warmup-msg-${index}`} className="form-group">
                <label htmlFor={`warmup-msg-${index}`}>Сообщение {index + 1}</label>
                <input
                  id={`warmup-msg-${index}`}
                  type="text"
                  value={(form.account_warmup_messages || [])[index] || ''}
                  onChange={(e) => {
                    const next = [...(form.account_warmup_messages || [])];
                    next[index] = e.target.value;
                    setForm((prev) => ({ ...prev, account_warmup_messages: next }));
                  }}
                  placeholder={index === 0 ? 'Привет' : index === 1 ? 'Как дела?' : 'Что нового?'}
                />
              </div>
            ))}
          </div>
        ) : null}

        <div className="settings-actions">
          <button type="submit" className="btn btn-black" disabled={isSaving}>
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </form>

      <CustomAutomationIntegrationsBlock
        automationId={id}
        settings={settings}
        onReloadSettings={loadSettings}
        onError={setError}
        onMessage={setSuccess}
      />

      {isAdmin ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Доступ клиента</h3>
          {settings.solution_kind === 'dmp_bot' ? (
            <p className="form-hint">Эти логин и пароль бот спрашивает в Telegram, прежде чем слать лидов.</p>
          ) : null}
          <form onSubmit={handleCreateAccess}>
            <div className="form-group">
              <label htmlFor="access-login">Логин</label>
              <input
                id="access-login"
                type="text"
                value={newCredential.username}
                onChange={(e) => setNewCredential((prev) => ({ ...prev, username: e.target.value }))}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="access-password">Пароль</label>
              <input
                id="access-password"
                type="text"
                value={newCredential.password}
                onChange={(e) => setNewCredential((prev) => ({ ...prev, password: e.target.value }))}
                required
              />
            </div>
            <div className="settings-actions">
              <button type="submit" className="btn btn-black" disabled={isCreatingAccess}>
                {isCreatingAccess ? 'Создание...' : 'Выдать доступ'}
              </button>
            </div>
          </form>
          {credentials.length === 0 ? (
            <p className="form-hint">Пока нет логинов клиента.</p>
          ) : (
            <div className="crm-list" style={{ marginTop: 16 }}>
              {credentials.map((item) => (
                <div key={item.id} className="crm-item">
                  <div className="crm-item-header">
                    <strong>{item.username}</strong>
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={async () => {
                        if (!window.confirm('Удалить доступ?')) {
                          return;
                        }
                        await customService.deleteCredential(id, item.id);
                        await loadCredentials();
                      }}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationSettingsPage;
