import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { CF_CREDENTIAL_FIELDS, CF_PLATFORMS, accountStatusLabel, formatWhen } from './contentFactoryLabels';
import '../../../styles/customAccountManager.css';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customContentFactory.css';

const emptyForm = {
  platform: 'youtube',
  display_name: '',
  handle: '',
  external_id: '',
  access_token: '',
  refresh_token: '',
  ig_user_id: '',
  board_id: '',
  group_id: '',
};

const CustomAutomationContentFactoryAccountsPage = () => {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [accounts, setAccounts] = useState([]);
  const [oauthReady, setOauthReady] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadAccounts = useCallback(async () => {
    const data = await customService.getContentFactoryAccounts(id);
    setAccounts(data.items || []);
    setOauthReady(Boolean(data.youtube_oauth_ready));
  }, [id]);

  useEffect(() => {
    loadAccounts().catch((err) => setError(err.message || 'Не удалось загрузить аккаунты'));
  }, [loadAccounts]);

  useEffect(() => {
    if (searchParams.get('youtube') === 'connected') {
      setMessage('YouTube подключён и поставлен на прогрев');
      const next = new URLSearchParams(searchParams);
      next.delete('youtube');
      next.delete('account_id');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const credentialsFor = () => {
    const credentials = {};
    if (form.access_token.trim()) credentials.access_token = form.access_token.trim();
    if (form.refresh_token.trim()) credentials.refresh_token = form.refresh_token.trim();
    if (form.ig_user_id.trim()) credentials.ig_user_id = form.ig_user_id.trim();
    if (form.board_id.trim()) credentials.board_id = form.board_id.trim();
    if (form.group_id.trim()) credentials.group_id = form.group_id.trim();
    return credentials;
  };

  const handleConnect = async (event) => {
    event.preventDefault();
    const credentials = credentialsFor();
    if (form.platform === 'youtube' && !credentials.refresh_token && !credentials.access_token) {
      setError('YouTube: вставьте refresh token или access token, либо пройдите OAuth');
      return;
    }
    if (form.platform === 'instagram' && (!credentials.access_token || !credentials.ig_user_id)) {
      setError('Instagram: нужны access token и Instagram User ID');
      return;
    }
    if (form.platform === 'tiktok' && !credentials.access_token) {
      setError('TikTok: нужен access token');
      return;
    }
    if (form.platform === 'pinterest' && (!credentials.access_token || !credentials.board_id)) {
      setError('Pinterest: нужны access token и board_id');
      return;
    }
    if (form.platform === 'vk' && (!credentials.access_token || !credentials.group_id)) {
      setError('VK Клипы: нужен пользовательский токен и id сообщества');
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await customService.connectContentFactoryAccount(id, {
        platform: form.platform,
        display_name: form.display_name,
        handle: form.handle,
        external_id: form.external_id || form.ig_user_id || form.group_id,
        credentials,
      });
      setForm({ ...emptyForm, platform: form.platform });
      setMessage('Аккаунт подключён и поставлен на прогрев');
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось подключить');
    } finally {
      setBusy(false);
    }
  };

  const handleYoutubeOauth = async () => {
    setBusy(true);
    setError(null);
    try {
      const returnUrl = `${window.location.origin}${NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY_ACCOUNTS(id)}`;
      const data = await customService.startContentFactoryYoutubeOauth(id, returnUrl);
      if (data.auth_url) {
        window.location.assign(data.auth_url);
        return;
      }
      setError('OAuth URL не получен');
    } catch (err) {
      setError(err.message || 'OAuth недоступен');
    } finally {
      setBusy(false);
    }
  };

  const patchAccount = async (accountId, payload, okMessage) => {
    setBusy(true);
    setError(null);
    try {
      await customService.updateContentFactoryAccount(id, accountId, payload);
      setMessage(okMessage);
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось обновить аккаунт');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (accountId) => {
    if (!window.confirm('Отключить этот аккаунт от завода?')) {
      return;
    }
    setBusy(true);
    try {
      await customService.deleteContentFactoryAccount(id, accountId);
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось удалить');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Аккаунты контент-завода</h1>
          <p>Новый аккаунт сначала прогревается: без холодного постинга, чтобы не словить теневой бан.</p>
        </div>
        <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY(id)}>
          Результаты
        </Link>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="cf-grid-2">
        {CF_PLATFORMS.map((item) => (
          <div className="cf-platform-card" key={item.id}>
            <h3>{item.title}</h3>
            <p className="cf-muted">{item.hint}</p>
            <p className="cf-muted">
              Подключено: {accounts.filter((account) => account.platform === item.id).length}
            </p>
          </div>
        ))}
      </div>

      <form className="ubt-panel" onSubmit={handleConnect}>
        <div className="ubt-panel-header">
          <div>
            <h2>Подключить аккаунт</h2>
            <p>
              Токены шифруются и обратно не показываются. Для {CF_PLATFORMS.find((item) => item.id === form.platform)?.title}: {CF_CREDENTIAL_FIELDS[form.platform]}.
            </p>
          </div>
        </div>
        <div className="cf-form-grid">
          <div className="form-group">
            <label htmlFor="cf-platform">Площадка</label>
            <CustomSelect
              id="cf-platform"
              value={form.platform}
              options={CF_PLATFORMS.map((item) => ({ value: item.id, label: item.title }))}
              onChange={(event) => setForm((current) => ({ ...current, platform: event.target.value }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="cf-name">Название</label>
            <input
              id="cf-name"
              value={form.display_name}
              onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
              placeholder="Канал / бренд"
            />
          </div>
          <div className="form-group">
            <label htmlFor="cf-handle">Хэндл</label>
            <input
              id="cf-handle"
              value={form.handle}
              onChange={(event) => setForm((current) => ({ ...current, handle: event.target.value }))}
              placeholder="@channel"
            />
          </div>
          <div className="form-group">
            <label htmlFor="cf-token">Access token</label>
            <input
              id="cf-token"
              type="password"
              value={form.access_token}
              onChange={(event) => setForm((current) => ({ ...current, access_token: event.target.value }))}
              autoComplete="off"
            />
          </div>
          {form.platform === 'youtube' ? (
            <div className="form-group">
              <label htmlFor="cf-refresh">Refresh token</label>
              <input
                id="cf-refresh"
                type="password"
                value={form.refresh_token}
                onChange={(event) => setForm((current) => ({ ...current, refresh_token: event.target.value }))}
                autoComplete="off"
              />
            </div>
          ) : null}
          {form.platform === 'instagram' ? (
            <div className="form-group">
              <label htmlFor="cf-ig">Instagram User ID</label>
              <input
                id="cf-ig"
                value={form.ig_user_id}
                onChange={(event) => setForm((current) => ({ ...current, ig_user_id: event.target.value }))}
              />
            </div>
          ) : null}
          {form.platform === 'vk' ? (
            <div className="form-group">
              <label htmlFor="cf-group">ID сообщества</label>
              <input
                id="cf-group"
                value={form.group_id}
                onChange={(event) => setForm((current) => ({ ...current, group_id: event.target.value }))}
                placeholder="123456789 или club123456789"
              />
            </div>
          ) : null}
          {form.platform === 'pinterest' ? (
            <div className="form-group">
              <label htmlFor="cf-board">Board ID</label>
              <input
                id="cf-board"
                value={form.board_id}
                onChange={(event) => setForm((current) => ({ ...current, board_id: event.target.value }))}
              />
            </div>
          ) : null}
        </div>
        <div className="cf-actions">
          <button type="submit" className="btn btn-black" disabled={busy}>Подключить</button>
          {form.platform === 'youtube' && oauthReady ? (
            <button type="button" className="btn btn-outline" onClick={handleYoutubeOauth} disabled={busy}>
              YouTube OAuth
            </button>
          ) : null}
        </div>
      </form>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Подключённые</h2>
        </div>
        {accounts.length === 0 ? (
          <p className="ubt-empty">Пока нет аккаунтов — завод сможет генерировать, но публиковать будет некуда.</p>
        ) : (
          <div className="cf-video-list">
            {accounts.map((account) => {
              const percent = account.warmup?.percent || 0;
              return (
                <div className="cf-account-card" key={account.id}>
                  <div className="ubt-panel-header">
                    <div>
                      <h3>{account.display_name || account.handle || account.platform}</h3>
                      <p>{account.platform} {account.handle ? `· ${account.handle}` : ''}</p>
                    </div>
                    <span className={`cf-tag${account.status === 'shadow_risk' ? ' cf-tag--danger' : account.status === 'ready' ? ' cf-tag--ok' : ' cf-tag--warn'}`}>
                      {accountStatusLabel(account.status)}
                    </span>
                  </div>
                  <p className="cf-muted">Прогрев {percent}% · {account.warmup?.actions_done || 0}/{account.warmup?.actions_required || 0} действий · осталось дней: {account.warmup?.days_left ?? '—'}</p>
                  <div className="cf-bar"><span style={{ width: `${percent}%` }} /></div>
                  <div className="cf-meta">
                    <span>Здоровье {account.health_score}</span>
                    <span>Сегодня постов: {account.posts_today}</span>
                    <span>Последний пост: {formatWhen(account.last_posted_at)}</span>
                  </div>
                  {(account.warmup_events || []).length ? (
                    <div>
                      <p className="cf-muted">Последние действия прогрева</p>
                      {(account.warmup_events || []).slice(0, 4).map((event) => (
                        <p key={event.id} className="cf-muted">{formatWhen(event.created_at)} · {event.detail || event.action_type}</p>
                      ))}
                    </div>
                  ) : (
                    <p className="cf-muted">Журнал прогрева появится после первых тиков планировщика. Это учёт действий, не эмуляция приложения.</p>
                  )}
                  {account.last_error ? <p className="form-hint form-hint--error">{account.last_error}</p> : null}
                  <div className="cf-actions">
                    {account.status === 'paused' ? (
                      <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => patchAccount(account.id, { resume: true }, 'Аккаунт снят с паузы')}>
                        Снять паузу
                      </button>
                    ) : (
                      <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => patchAccount(account.id, { pause: true }, 'Аккаунт на паузе')}>
                        Пауза
                      </button>
                    )}
                    <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => handleDelete(account.id)}>
                      Отключить
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationContentFactoryAccountsPage;
