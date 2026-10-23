import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import UbtCurrentChats from '../../../components/custom/UbtCurrentChats';
import CustomSelect from '../../../components/CustomSelect';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import UbtJoinDelay from '../../../components/custom/UbtJoinDelay';
import UbtAccountPacing from '../../../components/custom/UbtAccountPacing';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { folderOptions, toggleNumericId, ubtModulePath } from './customNav';
import { humanizeUbtLog } from './ubtLogText';
import UbtDistributeChats from '../../../components/custom/UbtDistributeChats';
import UbtJobControls from '../../../components/custom/UbtJobControls';
import { assertCanRun, LIVE_JOB_STATUSES, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const STATUS_LABELS = {
  pending: 'Ожидает',
  running: 'В работе',
  paused: 'На паузе',
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

const CustomAutomationLeadInterceptPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [chatTab, setChatTab] = useState('links');
  const [links, setLinks] = useState('');
  const [folderId, setFolderId] = useState('');
  const [dbQuery, setDbQuery] = useState('');
  const [presetName, setPresetName] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
  };

  const load = useCallback(async () => {
    const payload = await customService.getChatMonitoringModule(id);
    applyPayload(payload);
    setError(null);
  }, [id]);

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Не удалось загрузить модуль'));
  }, [load]);

  const jobs = data?.jobs || [];
  const activeJob = jobs.find((item) => LIVE_JOB_STATUSES.includes(item.status)) || jobs[0] || null;

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
  const selectedChats = new Set(settings?.chat_ids || []);
  const selectedFolders = new Set(settings?.folder_ids || []);
  const blockedAccounts = new Set(settings?.blacklisted_account_ids || []);

  const accounts = useMemo(() => {
    const items = data?.accounts || [];
    const needle = accountQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (blockedAccounts.has(item.id)) {
        return false;
      }
      if (!item.eligible) {
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

  const dbChats = useMemo(() => {
    const items = data?.chats || [];
    const needle = dbQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (folderId && String(item.folder_id || '') !== String(folderId)) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.title} ${item.invite_link || ''}`.toLowerCase().includes(needle);
    });
  }, [data, dbQuery, folderId]);

  const chosenAccounts = (data?.accounts || []).filter((item) => selectedAccounts.has(item.id));
  const chosenChats = (data?.chats || []).filter((item) => selectedChats.has(item.id));
  const issues = data?.issues || [];
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);

  const persist = async (next = {}) => {
    const payload = { ...settingsRef.current, enabled: enabledRef.current, ...next };
    const result = await customService.saveChatMonitoringModule(id, payload);
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
      setError(err.message || 'Ошибка');
      return null;
    } finally {
      setBusy(false);
    }
  };

  const toggleAccount = (accountId) => patch({ account_ids: toggleNumericId(settings.account_ids, accountId) });
  const toggleChat = (chatId) => patch({ chat_ids: toggleNumericId(settings.chat_ids, chatId) });
  const toggleFolder = (value) => patch({ folder_ids: toggleNumericId(settings.folder_ids, value) });

  if (!data || !settings) {
    return <div className="nc-page"><p className="nc-muted">{error || 'Загрузка...'}</p></div>;
  }

  return (
    <div className="nc-page">
      <div className="nc-head">
        <div>
          <p className="nc-kicker">Телеграм УБТ</p>
          <h1>Перехват заявок</h1>
          <p className="nc-intro">
            Выбранные аккаунты сидят в целевых чатах и слушают сообщения. Если человек прямо или косвенно ищет услугу —
            один из этих аккаунтов пишет ему в ЛС. Карточка с датой, профилем, телефоном и перепиской уходит в тот же Telegram-бот,
            что и номера из DMP. Эти же аккаунты квалифицируют номера DMP, когда прозвон Sasha AI выключен.
          </p>
        </div>
        <FeatureToggle compact title="Модуль включён" checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }).catch((err) => setError(err.message || 'Не удалось сохранить')); }} />
      </div>
      {error ? <div className="nc-alert">{error}</div> : null}
      {message ? <p className="nc-muted">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head"><h2>Аккаунты, которые пишут лиду</h2></div>
        <p className="nc-muted">Они же вступают в чаты и слушают. ЛС уходит одному из выбранных, не обязательно тому, кто увидел сообщение.</p>
        <div className="nc-split" style={{ marginTop: 12 }}>
          <div className="nc-pane">
            <input className="nc-search" value={accountQuery} onChange={(event) => setAccountQuery(event.target.value)} placeholder="Поиск аккаунта" />
            <div className="nc-list" style={{ marginTop: 8 }}>
              {accounts.map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedAccounts.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleAccount(item.id)}>
                  <div>
                    <strong>{item.label}</strong>
                    <span>{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`}</span>
                  </div>
                  <span>{item.eligible ? 'доступен' : 'недоступен'}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Выбрано {chosenAccounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: [] })}>Очистить</button>
            </div>
            {chosenAccounts.length === 0 ? <div className="nc-empty">Аккаунты не выбраны</div> : (
              <div className="nc-list">
                {chosenAccounts.map((item) => (
                  <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleAccount(item.id)}>
                    <div><strong>{item.label}</strong></div>
                    <span>×</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="nc-row" style={{ marginTop: 12 }}>
          <span className="nc-muted">Заготовки</span>
          {(settings.presets || []).map((item) => (
            <button key={item.name} type="button" className="nc-chip" onClick={() => { setSettings({ ...item.settings, presets: settings.presets }); setDirty(true); }}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Имя" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); const payload = await customService.saveChatMonitoringPreset(id, presetName); applyPayload(payload); return payload; }, 'Заготовка сохранена')}>Сохранить</button>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Целевые чаты <span className="nc-muted">{selectedFolders.size} пап. · {selectedChats.size} чатов</span></h2>
          <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты и каналы</Link>
        </div>
        <div className="nc-row">
          <button type="button" className={`nc-chip ${chatTab === 'links' ? 'is-on' : ''}`} onClick={() => setChatTab('links')}>Ссылка</button>
          <button type="button" className={`nc-chip ${chatTab === 'folder' ? 'is-on' : ''}`} onClick={() => setChatTab('folder')}>Папки</button>
        </div>
        {chatTab === 'links' ? (
          <div style={{ marginTop: 12 }}>
            <textarea className="nc-area" value={links} onChange={(event) => setLinks(event.target.value)} placeholder="@chat или https://t.me/chat" />
            <div className="nc-row" style={{ marginTop: 8 }}>
              <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addChatMonitoringGroups(id, links).then((payload) => { applyPayload(payload); setLinks(''); return payload; }), 'Чаты добавлены')}>+ Добавить</button>
            </div>
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            <UbtFolderPicker folders={data.folders} selectedIds={selectedFolders} onToggle={toggleFolder} />
            <div className="nc-row" style={{ marginTop: 12 }}>
              <CustomSelect className="nc-select" value={String(folderId || '')} options={folderOptions(data.folders, 'Чаты внутри папки')} onChange={(event) => setFolderId(event.target.value)} />
              <input className="nc-search" value={dbQuery} onChange={(event) => setDbQuery(event.target.value)} placeholder="Поиск чата" />
            </div>
            <div className="nc-list" style={{ marginTop: 8 }}>
              {dbChats.map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.is_group === false ? 'канал — будет пропущен' : item.join_status}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
        {chosenChats.length ? (
          <div className="nc-list" style={{ marginTop: 12 }}>
            {chosenChats.map((item) => (
              <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleChat(item.id)}>
                <div><strong>{item.title}</strong><span>{item.invite_link || ''}</span></div>
                <span>×</span>
              </button>
            ))}
          </div>
        ) : null}
        <UbtDistributeChats
          automationId={id}
          taskKey="chat_monitoring"
          accounts={data.accounts || []}
          chats={data.chats || []}
          folders={data.folders || []}
          settings={settings}
          onChange={(partial) => patch(partial)}
        />
        <UbtJoinDelay settings={settings} onPatch={patch} />
        <UbtAccountPacing settings={settings} onPatch={patch} noun="ЛС" />
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Оффер и фильтр</h2></div>
        <p className="nc-muted">
          Слова — подсказка модели, что вы продаёте. Сообщение не обязано их содержать: «кто знает где сделать» тоже уйдёт в классификатор.
          Флуд без запроса в ЛС не пишется.
        </p>
        <textarea
          className="nc-area"
          style={{ marginTop: 12 }}
          value={(settings.keywords || []).join(', ')}
          onChange={(event) => patch({ keywords: event.target.value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean) })}
          placeholder="seo, сайт, продвижение — темы оффера"
        />
        <div style={{ marginTop: 12 }}>
          <FeatureToggle compact title="Ночной простой" description="Ночью по Москве в ЛС не пишем." checked={Boolean(settings.respect_night_hours)} onChange={(value) => persistFlag({ respect_night_hours: value })} />
          <div style={{ marginTop: 8 }}>
            <UbtCurrentChats checked={settings.include_joined} onChange={(value) => persistFlag({ include_joined: value })} />
          </div>
        </div>
        <p className="nc-muted" style={{ marginTop: 10 }}>
          Навыки триггера и первого ЛС — в <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)}>скиллбейзе</Link>.
          Переписка после первого касания — прогрев лида, не продажа.
        </p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{selectedFolders.size || selectedChats.size}</strong><span>Чаты</span></div>
          <div className="nc-kpi"><strong>{data.summary?.leads || 0}</strong><span>Лиды</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>ЛС ушло</span></div>
        </div>
        {issues.length ? (
          <div className="nc-alert" style={{ marginTop: 12 }}>
            <strong>Чтобы запустить</strong>
            {issues.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        <div className="nc-logs" style={{ marginTop: 12 }}>
          {(activeJob?.logs || []).length === 0 ? 'После запуска здесь будет: увидел заявку → передал аккаунту → написал в ЛС.' : (activeJob.logs || []).map((row, index) => (
            <div key={`${row.ts}-${index}`} className={row.level === 'error' ? 'nc-log-err' : ''}>{formatWhen(row.ts)} {humanizeUbtLog(row.message)}</div>
          ))}
        </div>
        <UbtUnsaved dirty={dirty} />
        <div className="nc-launch" style={{ marginTop: 12 }}>
          <div className="nc-status">
            <span className={`nc-dot ${activeJob && ['pending', 'running'].includes(activeJob.status) ? 'is-on' : ''}`} />
            {activeJob ? `${STATUS_LABELS[activeJob.status] || activeJob.status} · ${formatWhen(activeJob.created_at)}` : 'Остановлено'}
          </div>
          <div className="nc-row">
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => persist(), 'Сохранено')}>Сохранить</button>
            <UbtJobControls
              job={activeJob}
              busy={busy}
              onPause={() => runSafe(() => customService.pauseAutomationJob(id, activeJob.id).then(load), 'На паузе')}
              onResume={() => runSafe(() => customService.resumeAutomationJob(id, activeJob.id).then(load), 'Продолжено')}
              onCancel={() => runSafe(() => customService.cancelAutomationJob(id, activeJob.id).then(load), 'Остановлено')}
            />
            <button
              type="button"
              className="acc-btn acc-btn--primary"
              disabled={busy || !enabled || (issues.length > 0 && !dirty)}
              onClick={() => runSafe(async () => {
                const saved = assertCanRun(await persist());
                await customService.runChatMonitoringModule(id, { ...saved.settings, enabled: saved.enabled });
                await load();
              }, 'Слушаем чаты')}
            >
              Слушать чаты
            </button>
            <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id)}>Лиды</Link>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'tasks')}>Задачи</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationLeadInterceptPage;
