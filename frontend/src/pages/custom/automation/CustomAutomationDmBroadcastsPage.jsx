import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { toggleNumericId, ubtModulePath } from './customNav';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_peer_min: 15, delay_peer_max: 40, delay_msg_min: 2, delay_msg_max: 4 },
  rec: { delay_peer_min: 30, delay_peer_max: 90, delay_msg_min: 3, delay_msg_max: 8 },
  max: { delay_peer_min: 60, delay_peer_max: 180, delay_msg_min: 6, delay_msg_max: 16 },
};

const STATUS_LABELS = {
  pending: 'Ожидает',
  running: 'В работе',
  completed: 'Завершено',
  error: 'Ошибка',
  cancelled: 'Отменено',
  skipped: 'Пропущено',
};

const formatWhen = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const CustomAutomationDmBroadcastsPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [recipientDraft, setRecipientDraft] = useState('');
  const [presetName, setPresetName] = useState('');
  const [blackAccountQuery, setBlackAccountQuery] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
  };

  const load = useCallback(async () => {
    const payload = await customService.getDmBroadcastsModule(id);
    applyPayload(payload);
    setError(null);
  }, [id]);

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Не удалось загрузить модуль'));
  }, [load]);

  const jobs = data?.jobs || [];
  const activeJob = jobs.find((item) => ['pending', 'running'].includes(item.status)) || jobs[0] || null;

  useEffect(() => {
    if (!jobs.some((item) => ['pending', 'running'].includes(item.status))) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      load().catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [jobs, load]);

  const patch = (partial) => {
    setSettings((prev) => ({ ...prev, ...partial }));
    setDirty(true);
  };
  const selectedAccounts = new Set(settings?.account_ids || []);
  const blockedAccounts = new Set(settings?.blacklisted_account_ids || []);
  const selectedUserFolders = new Set(settings?.user_folder_ids || []);
  const messages = settings?.messages || [];
  const recipients = settings?.recipients || [];

  const accounts = useMemo(() => {
    const items = data?.accounts || [];
    const needle = accountQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (blockedAccounts.has(item.id)) {
        return false;
      }
      if (settings?.require_proxy && !item.has_proxy) {
        return false;
      }
      if (settings?.hide_in_work && item.in_work) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.label} ${item.username || ''} ${item.phone_number || ''} ${item.id}`.toLowerCase().includes(needle);
    });
  }, [data, accountQuery, settings, blockedAccounts]);

  const chosenAccounts = (data?.accounts || []).filter((item) => selectedAccounts.has(item.id));
  const blockedAccountRows = (data?.accounts || []).filter((item) => blockedAccounts.has(item.id));
  const issues = data?.issues || [];
  const deliveredIds = new Set((data?.summary?.delivered_ids || []).map((item) => String(item).toLowerCase()));
  const remaining = recipients.filter((item) => !deliveredIds.has(String(item).toLowerCase())).length;
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);

  const persist = async (next = {}) => {
    const payload = { ...settingsRef.current, enabled: enabledRef.current, ...next };
    const result = await customService.saveDmBroadcastsModule(id, payload);
    applyPayload(result);
    setDirty(false);
    return result;
  };

  const persistFlag = (partial) => {
    setSettings(mergeSettings(settingsRef, partial));
    persist(partial).catch((err) => setError(err.message || 'Не удалось сохранить'));
  };

  const runSafe = async (fn, okText) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await fn();
      if (okText) {
        setMessage(okText);
      }
      return result;
    } catch (err) {
      setError(err.message || 'Не удалось выполнить действие');
      return null;
    } finally {
      setBusy(false);
    }
  };

  const toggleAccount = (accountId) => {
    const next = selectedAccounts.has(accountId)
      ? settings.account_ids.filter((item) => item !== accountId)
      : [...settings.account_ids, accountId];
    patch({ account_ids: next });
  };

  const blockAccount = (accountId) => {
    patch({
      blacklisted_account_ids: blockedAccounts.has(accountId)
        ? settings.blacklisted_account_ids.filter((item) => item !== accountId)
        : [...(settings.blacklisted_account_ids || []), accountId],
      account_ids: settings.account_ids.filter((item) => item !== accountId),
    });
  };

  const updateMessage = (index, text) => {
    const next = messages.map((item, idx) => (idx === index ? { text } : item));
    patch({ messages: next });
  };

  const addMessage = () => {
    if (messages.length >= 10) {
      return;
    }
    patch({ messages: [...messages, { text: '' }] });
  };

  const removeMessage = (index) => {
    patch({ messages: messages.filter((_, idx) => idx !== index) });
  };

  const removeRecipient = (value) => {
    patch({ recipients: recipients.filter((item) => item !== value) });
  };

  const toggleUserFolder = (folderId) => {
    patch({ user_folder_ids: toggleNumericId(settings.user_folder_ids, folderId) });
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка ЛС-рассылки...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>ЛС-рассылки</h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <p className="nc-intro">Массовая рассылка цепочки личных сообщений. Перед отправкой аккаунт открывает профиль, печатает и пишет как человек. Лимиты — у этой задачи, рабочие часы общие.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Аккаунты <span className="nc-muted">{selectedAccounts.size} выбрано</span></h2>
        </div>
        <div className="nc-split">
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Доступные аккаунты {accounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => load()}>Обновить</button>
            </div>
            <div className="nc-row">
              <input className="nc-search" value={accountQuery} onChange={(event) => setAccountQuery(event.target.value)} placeholder="Поиск по ID, телефону, username..." />
            </div>
            <div className="nc-row">
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: accounts.filter((item) => item.eligible).map((item) => item.id) })}>Добавить все</button>
              <UbtCheck checked={Boolean(settings.require_proxy)} onChange={(value) => persistFlag({ require_proxy: value })}>Рабочие прокси</UbtCheck>
              <UbtCheck checked={Boolean(settings.hide_in_work)} onChange={(value) => persistFlag({ hide_in_work: value })}>Скрыть в работе</UbtCheck>
            </div>
            {accounts.length === 0 ? <div className="nc-empty">Нет рабочих аккаунтов</div> : (
              <div className="nc-list">
                {accounts.map((item) => (
                  <button key={item.id} type="button" className={`nc-item ${selectedAccounts.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`} · {item.proxy_label || 'без прокси'}</span>
                    </div>
                    <span>{item.in_work ? 'в работе' : item.eligible ? 'доступен' : 'недоступен'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Выбрано для ЛС-рассылки {chosenAccounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: [] })}>Удалить все</button>
            </div>
            {chosenAccounts.length === 0 ? <div className="nc-empty">Аккаунты не выбраны</div> : (
              <div className="nc-list">
                {chosenAccounts.map((item) => (
                  <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.daily_messages_sent || 0} действий сегодня</span>
                    </div>
                    <span>×</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="nc-row" style={{ marginTop: 12 }}>
          <span className="nc-muted">Заготовки запуска</span>
          {(settings.presets || []).map((item) => (
            <button key={item.name} type="button" className="nc-chip" onClick={() => { setSettings({ ...item.settings, presets: settings.presets }); setDirty(true); }}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Название заготовки" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveDmBroadcastsPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head">
            <h2>Получатели <span className="nc-muted">{recipients.length}</span></h2>
          </div>
          <textarea className="nc-area" value={recipientDraft} onChange={(event) => setRecipientDraft(event.target.value)} placeholder="@username, t.me/user — через пробел или с новой строки" />
          <div className="nc-row" style={{ marginTop: 8 }}>
            <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addDmBroadcastsRecipients(id, recipientDraft).then((payload) => { applyPayload(payload); setRecipientDraft(''); return payload; }), 'Получатели добавлены')}>+ Добавить</button>
            <span className="nc-muted">Строк: {recipientDraft.split(/[\s,]+/).filter((item) => item.trim()).length}</span>
          </div>
          {recipients.length === 0 ? <div className="nc-empty" style={{ marginTop: 12 }}>Список пуст</div> : (
            <div className="nc-list" style={{ marginTop: 12 }}>
              {recipients.map((item) => (
                <button key={item} type="button" className="nc-item is-on" onClick={() => removeRecipient(item)}>
                  <div><strong>{item}</strong><span>{deliveredIds.has(String(item).toLowerCase()) ? 'доставлено' : 'в очереди'}</span></div>
                  <span>×</span>
                </button>
              ))}
            </div>
          )}
          <p className="nc-hint" style={{ marginTop: 10 }}>Ещё не разослано: {remaining}</p>
          <h3 className="nc-muted" style={{ marginTop: 16 }}>Папки из парсера юзеров</h3>
          <UbtFolderPicker kind="users" folders={data.user_folders} selectedIds={selectedUserFolders} onToggle={toggleUserFolder} />
        </div>

        <div className="nc-card">
          <div className="nc-card-head"><h2>Настройки отправки</h2></div>
          <div className="nc-mode" style={{ marginTop: 10 }}>
            <button type="button" className={settings.first_mode !== 'ai' ? 'is-on' : ''} onClick={() => patch({ first_mode: 'template' })}>Мой текст / шаблон</button>
            <button type="button" className={settings.first_mode === 'ai' ? 'is-on' : ''} onClick={() => patch({ first_mode: 'ai' })}>ИИ под каждого</button>
          </div>
          <div className="nc-card-head" style={{ marginTop: 16 }}>
            <h2>Цепочка сообщений</h2>
            <span className="nc-muted">{messages.length} сообщений</span>
          </div>
          {messages.length === 0 ? (
            <div className="nc-empty">Цепочка пуста — добавьте первое сообщение</div>
          ) : (
            <div className="nc-chain">
              {messages.map((item, index) => (
                <div key={`msg-${index}`} className="nc-chain-item">
                  <textarea className="nc-area" value={item.text || ''} onChange={(event) => updateMessage(index, event.target.value)} placeholder={index === 0 && settings.first_mode === 'ai' ? 'Подсказка тона для ИИ (необязательно)' : `Сообщение ${index + 1}`} />
                  <button type="button" className="nc-chain-remove" onClick={() => removeMessage(index)}>×</button>
                </div>
              ))}
            </div>
          )}
          <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 8 }} onClick={addMessage}>+ Сообщение</button>
          <p className="nc-hint">Переменные: {'{username}'}, {'{peer}'}, {'{my_name}'}. Спинтакс {'{привет|хай}'}.</p>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Лимиты задачи</h2></div>
        <div className="nc-mode">
          <button type="button" className={settings.work_mode !== 'time' ? 'is-on' : ''} onClick={() => patch({ work_mode: 'count' })}># По количеству</button>
          <button type="button" className={settings.work_mode === 'time' ? 'is-on' : ''} onClick={() => patch({ work_mode: 'time' })}>По времени</button>
        </div>
        {settings.work_mode === 'time' ? (
          <div className="nc-row" style={{ marginTop: 12 }}>
            <label className="nc-muted">Остановить после</label>
            <input className="nc-input" type="datetime-local" value={settings.end_at || ''} onChange={(event) => patch({ end_at: event.target.value })} />
          </div>
        ) : (
          <div className="nc-row" style={{ marginTop: 12 }}>
            <span className="nc-muted">Макс. сообщений за проход</span>
            <Stepper value={settings.max_messages} min={1} max={500} onChange={(value) => patch({ max_messages: value })} />
          </div>
        )}
        <div className="nc-row" style={{ marginTop: 12 }}>
          <span className="nc-muted">Пауза между получателями, сек</span>
          <input className="nc-input" type="number" min="0" value={settings.delay_peer_min} onChange={(event) => patch({ delay_peer_min: Number(event.target.value) })} />
          <span>—</span>
          <input className="nc-input" type="number" min="0" value={settings.delay_peer_max} onChange={(event) => patch({ delay_peer_max: Number(event.target.value) })} />
        </div>
        <div className="nc-row" style={{ marginTop: 8 }}>
          <span className="nc-muted">Пауза в цепочке, сек</span>
          <input className="nc-input" type="number" min="0" value={settings.delay_msg_min} onChange={(event) => patch({ delay_msg_min: Number(event.target.value) })} />
          <span>—</span>
          <input className="nc-input" type="number" min="0" value={settings.delay_msg_max} onChange={(event) => patch({ delay_msg_max: Number(event.target.value) })} />
        </div>
        <div className="nc-row" style={{ marginTop: 8 }}>
          <button type="button" className="nc-chip" onClick={() => patch(DELAY_PRESETS.min)}>Быстрее</button>
          <button type="button" className="nc-chip" onClick={() => patch(DELAY_PRESETS.rec)}>Рекомендуемые</button>
          <button type="button" className="nc-chip" onClick={() => patch(DELAY_PRESETS.max)}>Медленнее</button>
        </div>
        <div className="nc-row" style={{ marginTop: 12 }}>
          <UbtCheck checked={Boolean(settings.skip_sent)} onChange={(value) => persistFlag({ skip_sent: value })}>Пропускать уже отправленные</UbtCheck>
          <UbtCheck checked={Boolean(settings.skip_errors)} onChange={(value) => persistFlag({ skip_errors: value })}>Пропускать ошибки</UbtCheck>
          <UbtCheck checked={Boolean(settings.limit_rate)} onChange={(value) => persistFlag({ limit_rate: value })}>Учитывать лимиты аккаунта</UbtCheck>
          <UbtCheck checked={Boolean(settings.respect_night_hours)} onChange={(value) => persistFlag({ respect_night_hours: value })}>Ночной простой (21:30–07:00 МСК)</UbtCheck>
        </div>
        {issues.length ? (
          <ul className="nc-issues">
            {issues.map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : null}
        <div className="nc-kpis" style={{ marginTop: 12 }}>
          <div className="nc-kpi"><strong>{settings.work_mode === 'time' ? 'окно' : settings.max_messages}</strong><span>Макс. отправок</span></div>
          <div className="nc-kpi"><strong>{recipients.length + selectedUserFolders.size}</strong><span>Получатели / папки</span></div>
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунтов</span></div>
        </div>
        <UbtUnsaved dirty={dirty} />
        <div className="nc-launch" style={{ marginTop: 12 }}>
          <div className="nc-status">
            <span className={`nc-dot ${activeJob && ['pending', 'running'].includes(activeJob.status) ? 'is-on' : ''}`} />
            {activeJob ? `${STATUS_LABELS[activeJob.status] || activeJob.status} · ${formatWhen(activeJob.created_at)}` : 'Остановлено'}
          </div>
          <div className="nc-row">
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => persist()}>Сохранить</button>
            {activeJob?.can_cancel ? (
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.cancelAutomationJob(id, activeJob.id).then(load), 'Запуск отменён')}>Остановить</button>
            ) : null}
            <button
              type="button"
              className="acc-btn acc-btn--primary"
              disabled={busy || !enabled || (issues.length > 0 && !dirty)}
              onClick={() => runSafe(async () => {
                const saved = assertCanRun(await persist());
                await customService.runDmBroadcastsModule(id, { ...saved.settings, enabled: saved.enabled });
                await load();
              }, 'Запуск поставлен в очередь')}
            >
              + Новый запуск
            </button>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'tasks')}>Все задачи</Link>
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Статистика</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=dm_broadcast`}>История рассылок</Link>
        </div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Успешных</span></div>
          <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Неуспешных</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success_pct || 0}%</strong><span>Процент успешных</span></div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Чёрный список аккаунтов</h2></div>
        <div className="nc-row">
          <input className="nc-search" value={blackAccountQuery} onChange={(event) => setBlackAccountQuery(event.target.value)} placeholder="ID, username или телефон" />
          <button
            type="button"
            className="acc-btn acc-btn--ghost"
            onClick={() => {
              const needle = blackAccountQuery.trim().toLowerCase();
              if (!needle) {
                return;
              }
              const found = (data.accounts || []).find((item) => `${item.label} ${item.username || ''} ${item.phone_number || ''} ${item.id}`.toLowerCase().includes(needle));
              if (found) {
                blockAccount(found.id);
                setBlackAccountQuery('');
              }
            }}
          >
            + В ЧС
          </button>
        </div>
        {blockedAccountRows.length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Пусто</p> : (
          <div className="nc-list" style={{ marginTop: 10 }}>
            {blockedAccountRows.map((item) => (
              <button key={item.id} type="button" className="nc-item" onClick={() => blockAccount(item.id)}>
                <div><strong>{item.label}</strong><span>{item.username ? `@${item.username}` : item.phone_number}</span></div>
                <span>×</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationDmBroadcastsPage;
