import React, { useCallback, useEffect, useState } from 'react';
import customService from '../../../services/customService';
import CustomAutomationWebhookConstructor from './CustomAutomationWebhookConstructor';
import '../../../styles/customIntegrations.css';

const copyValue = async (value) => {
  if (!value) {
    return false;
  }
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
};

const CopyField = ({ id, label, value, hint }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const ok = await copyValue(value);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" value={value || ''} readOnly />
      {hint ? <span className="form-hint">{hint}</span> : null}
      <div className="settings-actions">
        <button type="button" className="acc-btn acc-btn--ghost" onClick={handleCopy} disabled={!value}>
          {copied ? 'Скопировано' : 'Копировать'}
        </button>
      </div>
    </div>
  );
};

const CustomAutomationIntegrationsBlock = ({
  automationId,
  settings,
  onReloadSettings,
  onError,
  onMessage,
  hideDmp = false,
}) => {
  const isDmpBot = settings?.solution_kind === 'dmp_bot';
  const [openTemplate, setOpenTemplate] = useState('');
  const [botPassword, setBotPassword] = useState('');
  const [connection, setConnection] = useState(null);
  const [amoForm, setAmoForm] = useState({
    subdomain: '',
    client_id: '',
    client_secret: '',
    pipeline_id: '',
    responsible_user_id: '',
    lead_status_id: '',
  });
  const [botToken, setBotToken] = useState('');
  const [sheetsForm, setSheetsForm] = useState({
    spreadsheet: '',
    worksheet: '',
    service_account_json: '',
  });
  const [isSavingCreds, setIsSavingCreds] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSavingPipeline, setIsSavingPipeline] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isRotating, setIsRotating] = useState(false);
  const [isSavingBot, setIsSavingBot] = useState(false);
  const [isSavingSheets, setIsSavingSheets] = useState(false);

  useEffect(() => {
    setSheetsForm((prev) => ({
      ...prev,
      spreadsheet: settings?.google_sheets_spreadsheet_id || prev.spreadsheet || '',
      worksheet: settings?.google_sheets_worksheet || prev.worksheet || 'Лиды',
    }));
  }, [settings?.google_sheets_spreadsheet_id, settings?.google_sheets_worksheet]);

  const loadConnection = useCallback(async () => {
    try {
      const data = await customService.getAmocrmConnection(automationId);
      setConnection(data);
      setAmoForm((prev) => ({
        ...prev,
        subdomain: data.subdomain || '',
        client_id: data.client_id || '',
        client_secret: '',
        pipeline_id: data.pipeline_id || '',
        responsible_user_id: data.responsible_user_id || '',
        lead_status_id: data.lead_status_id || '',
      }));
    } catch (err) {
      onError(err.message || 'Не удалось загрузить AmoCRM');
    }
  }, [automationId, onError]);

  useEffect(() => {
    if (!isDmpBot) {
      loadConnection();
    }
  }, [isDmpBot, loadConnection]);

  const handleAmoChange = (e) => {
    const { name, value } = e.target;
    setAmoForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveCredentials = async (e) => {
    e.preventDefault();
    setIsSavingCreds(true);
    try {
      await customService.saveAmocrmCredentials(automationId, {
        subdomain: amoForm.subdomain,
        client_id: amoForm.client_id,
        client_secret: amoForm.client_secret || undefined,
      });
      onMessage('Данные AmoCRM сохранены');
      await loadConnection();
      await onReloadSettings();
    } catch (err) {
      onError(err.message || 'Не удалось сохранить AmoCRM');
    } finally {
      setIsSavingCreds(false);
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      if (amoForm.subdomain && amoForm.client_id) {
        await customService.saveAmocrmCredentials(automationId, {
          subdomain: amoForm.subdomain,
          client_id: amoForm.client_id,
          client_secret: amoForm.client_secret || undefined,
        });
      }
      const returnUrl = `${window.location.origin}/custom/automations/${automationId}/integrations`;
      const data = await customService.startAmocrmOAuth(automationId, returnUrl);
      window.location.assign(data.auth_url);
    } catch (err) {
      onError(err.message || 'Не удалось начать подключение');
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Отключить AmoCRM?')) {
      return;
    }
    try {
      await customService.deleteAmocrmConnection(automationId);
      onMessage('AmoCRM отключено');
      await loadConnection();
      await onReloadSettings();
    } catch (err) {
      onError(err.message || 'Не удалось отключить AmoCRM');
    }
  };

  const handleSavePipeline = async (e) => {
    e.preventDefault();
    setIsSavingPipeline(true);
    try {
      await customService.saveAmocrmPipeline(automationId, {
        pipeline_id: amoForm.pipeline_id,
        responsible_user_id: amoForm.responsible_user_id,
        lead_status_id: amoForm.lead_status_id,
      });
      onMessage('Воронка сохранена');
      await loadConnection();
    } catch (err) {
      onError(err.message || 'Не удалось сохранить воронку');
    } finally {
      setIsSavingPipeline(false);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await customService.runAmocrmSync(automationId);
      onMessage('Синхронизация запущена');
    } catch (err) {
      onError(err.message || 'Синхронизация не удалась');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleRotateSecret = async () => {
    if (!window.confirm('Выпустить новый секрет? Старый URL перестанет работать.')) {
      return;
    }
    setIsRotating(true);
    try {
      await customService.rotateDmpWebhookSecret(automationId);
      onMessage('Секрет обновлён');
      await onReloadSettings();
    } catch (err) {
      onError(err.message || 'Не удалось обновить секрет');
    } finally {
      setIsRotating(false);
    }
  };

  const handleSaveBot = async (e) => {
    e.preventDefault();
    setIsSavingBot(true);
    try {
      await customService.saveTelegramBot(automationId, {
        bot_token: botToken || undefined,
        password: botPassword || undefined,
      });
      setBotToken('');
      setBotPassword('');
      onMessage(botToken ? 'Бот подключён, webhook установлен' : 'Настройки бота сохранены');
      await onReloadSettings();
    } catch (err) {
      onError(err.message || 'Не удалось подключить бота');
    } finally {
      setIsSavingBot(false);
    }
  };

  const handleDisconnectBot = async () => {
    if (!window.confirm('Отключить бота?')) {
      return;
    }
    setIsSavingBot(true);
    try {
      await customService.saveTelegramBot(automationId, { disconnect: true });
      setBotToken('');
      setBotPassword('');
      onMessage('Бот отключён');
      await onReloadSettings();
    } catch (err) {
      onError(err.message || 'Не удалось отключить бота');
    } finally {
      setIsSavingBot(false);
    }
  };

  const handleSaveSheets = async (e) => {
    e.preventDefault();
    setIsSavingSheets(true);
    try {
      await customService.saveGoogleSheets(automationId, {
        spreadsheet: sheetsForm.spreadsheet,
        worksheet: sheetsForm.worksheet,
        service_account_json: sheetsForm.service_account_json || undefined,
      });
      setSheetsForm((prev) => ({ ...prev, service_account_json: '' }));
      onMessage('Google Таблица сохранена');
      await onReloadSettings();
    } catch (err) {
      onError(err.message || 'Не удалось сохранить таблицу');
    } finally {
      setIsSavingSheets(false);
    }
  };

  const showDmp = !hideDmp && (Boolean(settings?.is_dmp_one_enabled) || isDmpBot);
  const showSheets = isDmpBot;
  const toggleTemplate = (name) => setOpenTemplate((prev) => (prev === name ? '' : name));

  return (
    <>
      <div className="int-templates">
        <button type="button" className={`int-card ${openTemplate === 'telegram' ? 'is-on' : ''}`} onClick={() => toggleTemplate('telegram')}>
          <strong>Telegram-бот</strong>
          <span>Готовый шаблон: клиент пишет боту, получает лиды и статусы.</span>
          <em className={settings?.telegram_bot_token_set ? '' : 'is-off'}>
            {settings?.telegram_bot_token_set
              ? `@${settings.telegram_bot_username || 'бот'} · подписано: ${settings.telegram_bot_subscribers || 0}`
              : 'Не подключён'}
          </em>
        </button>
        {isDmpBot ? null : (
          <button type="button" className={`int-card ${openTemplate === 'amocrm' ? 'is-on' : ''}`} onClick={() => toggleTemplate('amocrm')}>
            <strong>AmoCRM</strong>
            <span>Готовый шаблон: OAuth, воронка и передача сделок.</span>
            <em className={connection?.connected ? '' : 'is-off'}>
              {connection?.connected ? 'Подключено' : 'Не подключено'}
            </em>
          </button>
        )}
      </div>

      {openTemplate === 'telegram' ? (
        <div className="int-form">
          <h2>Telegram-бот</h2>
          <p className="form-hint">
            {settings?.telegram_bot_token_set
              ? `@${settings.telegram_bot_username || 'бот'} · подписано: ${settings.telegram_bot_subscribers || 0}`
              : 'Вставьте API-ключ бота — webhook поставится сам.'}
            {isDmpBot
              ? ' Логин и пароль клиент берёт из блока «Доступ клиента».'
              : ' Клиент пишет боту и вводит пароль. Если договорились — в чат уходят телефон, username и контекст, если нет — только телефон.'}
          </p>
          <form onSubmit={handleSaveBot}>
            <div className="form-group">
              <label htmlFor="telegram-bot-token">API-ключ</label>
              <input
                id="telegram-bot-token"
                type="password"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                placeholder={settings?.telegram_bot_token_set ? 'Оставьте пустым, чтобы не менять' : '123456:AA...'}
              />
            </div>
            {isDmpBot ? null : (
              <div className="form-group">
                <label htmlFor="telegram-bot-password">Пароль бота</label>
                <input
                  id="telegram-bot-password"
                  type="password"
                  value={botPassword}
                  onChange={(e) => setBotPassword(e.target.value)}
                  placeholder={settings?.telegram_bot_password_set ? 'Оставьте пустым, чтобы не менять' : 'Пароль, который вводит клиент'}
                />
              </div>
            )}
            {settings?.telegram_bot_webhook_url ? (
              <CopyField
                id="telegram-bot-webhook"
                label="Webhook"
                value={settings.telegram_bot_webhook_url}
              />
            ) : null}
            <div className="settings-actions">
              <button type="submit" className="acc-btn acc-btn--primary" disabled={isSavingBot || (!botToken && !botPassword && !settings?.telegram_bot_token_set)}>
                {isSavingBot ? 'Сохранение...' : 'Сохранить'}
              </button>
              {settings?.telegram_bot_token_set ? (
                <button type="button" className="acc-btn acc-btn--ghost" onClick={handleDisconnectBot} disabled={isSavingBot}>
                  Отключить
                </button>
              ) : null}
            </div>
          </form>
        </div>
      ) : null}

      {openTemplate === 'amocrm' && !isDmpBot ? (
        <div className="int-form">
          <h2>AmoCRM</h2>
          <p className="form-hint">{connection?.connected ? 'Подключено' : 'Не подключено'}</p>
          <form onSubmit={handleSaveCredentials}>
            <div className="form-group">
              <label htmlFor="amo-subdomain">Поддомен</label>
              <input
                id="amo-subdomain"
                name="subdomain"
                type="text"
                value={amoForm.subdomain}
                onChange={handleAmoChange}
                placeholder="company"
              />
            </div>
            <div className="form-group">
              <label htmlFor="amo-client-id">client_id</label>
              <input
                id="amo-client-id"
                name="client_id"
                type="text"
                value={amoForm.client_id}
                onChange={handleAmoChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="amo-client-secret">client_secret</label>
              <input
                id="amo-client-secret"
                name="client_secret"
                type="password"
                value={amoForm.client_secret}
                onChange={handleAmoChange}
                placeholder={connection?.client_secret_set ? 'Оставьте пустым, чтобы не менять' : ''}
              />
            </div>
            <CopyField
              id="amo-redirect"
              label="Redirect URI"
              value={connection?.redirect_uri || settings?.amocrm_redirect_uri || ''}
            />
            <div className="settings-actions">
              <button type="submit" className="acc-btn acc-btn--ghost" disabled={isSavingCreds}>
                {isSavingCreds ? 'Сохранение...' : 'Сохранить'}
              </button>
              <button type="button" className="acc-btn acc-btn--primary" onClick={handleConnect} disabled={isConnecting}>
                {isConnecting ? '...' : 'Подключить'}
              </button>
              {connection?.connected ? (
                <button type="button" className="acc-btn acc-btn--ghost" onClick={handleDisconnect}>
                  Отключить
                </button>
              ) : null}
            </div>
          </form>
          <form onSubmit={handleSavePipeline}>
            <div className="form-group">
              <label htmlFor="amo-pipeline">ID воронки</label>
              <input
                id="amo-pipeline"
                name="pipeline_id"
                type="text"
                value={amoForm.pipeline_id}
                onChange={handleAmoChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="amo-responsible">ID ответственного</label>
              <input
                id="amo-responsible"
                name="responsible_user_id"
                type="text"
                value={amoForm.responsible_user_id}
                onChange={handleAmoChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="amo-status">ID статуса сделки</label>
              <input
                id="amo-status"
                name="lead_status_id"
                type="text"
                value={amoForm.lead_status_id}
                onChange={handleAmoChange}
              />
            </div>
            <div className="settings-actions">
              <button type="submit" className="acc-btn acc-btn--ghost" disabled={isSavingPipeline}>
                {isSavingPipeline ? 'Сохранение...' : 'Сохранить воронку'}
              </button>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={handleSync} disabled={isSyncing || !connection?.connected}>
                {isSyncing ? '...' : 'Синхронизировать статусы'}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {showDmp ? (
        <div className="int-form">
          <h2>DMP.one</h2>
          <CopyField
            id="dmp-webhook-url"
            label="Вебхук"
            value={settings?.dmp_webhook_url || ''}
            hint="Вставьте в DMP One → Интеграция, JSON."
          />
          <CopyField
            id="dmp-webhook-secret"
            label="Секрет"
            value={settings?.dmp_webhook_secret || ''}
          />
          <div className="settings-actions">
            <button type="button" className="acc-btn acc-btn--ghost" onClick={handleRotateSecret} disabled={isRotating}>
              {isRotating ? '...' : 'Новый секрет'}
            </button>
          </div>
        </div>
      ) : null}

      {showSheets ? (
        <div className="int-form">
          <h2>Google Таблица</h2>
          <p className="form-hint">
            Один лид — одна строка. Лист по умолчанию «Лиды».
            {settings?.google_sheets_service_account_email
              ? ` Выдайте доступ редактора: ${settings.google_sheets_service_account_email}`
              : ''}
          </p>
          <form onSubmit={handleSaveSheets}>
            <div className="form-group">
              <label htmlFor="sheets-spreadsheet">Таблица (ссылка или ID)</label>
              <input
                id="sheets-spreadsheet"
                type="text"
                value={sheetsForm.spreadsheet}
                onChange={(e) => setSheetsForm((prev) => ({ ...prev, spreadsheet: e.target.value }))}
                placeholder="https://docs.google.com/spreadsheets/d/..."
              />
            </div>
            <div className="form-group">
              <label htmlFor="sheets-worksheet">Лист</label>
              <input
                id="sheets-worksheet"
                type="text"
                value={sheetsForm.worksheet}
                onChange={(e) => setSheetsForm((prev) => ({ ...prev, worksheet: e.target.value }))}
                placeholder="Лиды"
              />
            </div>
            <div className="form-group">
              <label htmlFor="sheets-json">JSON сервисного аккаунта</label>
              <textarea
                id="sheets-json"
                rows={6}
                value={sheetsForm.service_account_json}
                onChange={(e) => setSheetsForm((prev) => ({ ...prev, service_account_json: e.target.value }))}
                placeholder={settings?.google_sheets_credentials_set ? 'Оставьте пустым, чтобы не менять' : '{ "client_email": "...", "private_key": "..." }'}
              />
            </div>
            <div className="settings-actions">
              <button type="submit" className="acc-btn acc-btn--primary" disabled={isSavingSheets}>
                {isSavingSheets ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      <CustomAutomationWebhookConstructor
        automationId={automationId}
        onError={onError}
        onMessage={onMessage}
      />
    </>
  );
};

export default CustomAutomationIntegrationsBlock;
