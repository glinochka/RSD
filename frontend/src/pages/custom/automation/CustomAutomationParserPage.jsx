import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { toggleNumericId, ubtModulePath } from './customNav';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const SOURCES = [
  { value: 'messages', label: 'По сообщениям' },
  { value: 'participants', label: 'Участники' },
  { value: 'comments', label: 'По комментариям' },
];

const SINCE_OPTIONS = [
  { value: 1, label: '1 час' },
  { value: 6, label: '6 часов' },
  { value: 24, label: 'Сутки' },
  { value: 72, label: '3 дня' },
  { value: 168, label: 'Неделя' },
  { value: 720, label: '30 дней' },
];

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

const copyText = async (value) => {
  if (!value) {
    return;
  }
  await navigator.clipboard.writeText(value);
};

const CustomAutomationParserPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [presetName, setPresetName] = useState('');
  const [targetDraft, setTargetDraft] = useState('');
  const [folderQuery, setFolderQuery] = useState('');
  const [resultQuery, setResultQuery] = useState('');
  const [blackAccountQuery, setBlackAccountQuery] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
    setTargetDraft((payload.settings?.targets || []).join('\n'));
  };

  const load = useCallback(async () => {
    const payload = await customService.getParserModule(id);
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

  const folders = useMemo(() => {
    const items = data?.folders || [];
    const needle = folderQuery.trim().toLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((item) => `${item.name} ${item.id}`.toLowerCase().includes(needle));
  }, [data, folderQuery]);

  const chosenAccounts = (data?.accounts || []).filter((item) => selectedAccounts.has(item.id));
  const blockedAccountRows = (data?.accounts || []).filter((item) => blockedAccounts.has(item.id));
  const issues = data?.issues || [];
  const results = (data?.results || []).filter((item) => {
    const needle = resultQuery.trim().toLowerCase().replace(/^@/, '');
    if (!needle) {
      return true;
    }
    return `${item.title} ${item.username || ''} ${item.telegram_user_id} ${item.source_title || ''}`.toLowerCase().includes(needle);
  });
  const targetCount = targetDraft.split('\n').filter((item) => item.trim()).length + selectedChats.size + selectedFolders.size;
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);
  const targetDraftRef = useLiveRef(targetDraft);

  const persist = async (next = {}) => {
    const payload = {
      ...settingsRef.current,
      enabled: enabledRef.current,
      ...next,
      targets: (next.targets !== undefined ? next.targets : targetDraftRef.current.split('\n').map((item) => item.trim()).filter(Boolean)),
    };
    const result = await customService.saveParserModule(id, payload);
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

  const toggleFolder = (folderId) => {
    patch({ folder_ids: toggleNumericId(settings.folder_ids, folderId) });
  };

  const blockAccount = (accountId) => {
    patch({
      blacklisted_account_ids: blockedAccounts.has(accountId)
        ? settings.blacklisted_account_ids.filter((item) => item !== accountId)
        : [...(settings.blacklisted_account_ids || []), accountId],
      account_ids: settings.account_ids.filter((item) => item !== accountId),
    });
  };

  const exportCsv = () => {
    const header = ['telegram_id', 'username', 'link', 'name', 'chat', 'mode'];
    const lines = [header.join(',')];
    results.forEach((item) => {
      const cells = [
        item.telegram_user_id,
        item.username || '',
        item.link || '',
        item.title || '',
        item.source_title || '',
        item.source_mode || '',
      ].map((cell) => `"${String(cell).replace(/"/g, '""')}"`);
      lines.push(cells.join(','));
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'parser-users.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка парсера...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Парсер юзеров</h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <p className="nc-intro">Цели берём из «Чаты и каналы»: один файл — одна папка. Выберите папку, аккаунты вступят и соберут людей. После выполнения появится папка юзеров для ЛС-рассылок и масспрайминга.</p>
        <div className="nc-mode nc-mode--3" style={{ marginTop: 12 }}>
          {SOURCES.map((item) => (
            <button key={item.value} type="button" className={settings.source === item.value ? 'is-on' : ''} onClick={() => patch({ source: item.value })}>{item.label}</button>
          ))}
        </div>
        <p className="nc-hint" style={{ marginTop: 10 }}>
          {settings.source === 'messages' ? 'Основной режим: кто оставлял сообщения в окне времени.' : null}
          {settings.source === 'participants' ? 'Список участников на сейчас. Не обязан писать в чат.' : null}
          {settings.source === 'comments' ? 'Авторы комментариев под постами канала в том же окне времени.' : null}
        </p>
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
            <p className="nc-hint">Отфильтровано: {accounts.length} / Всего: {(data.accounts || []).length}</p>
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
              <strong>Выбрано для парсера {chosenAccounts.length}</strong>
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
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Заготовки запуска</h2>
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveParserPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
        </div>
        {(settings.presets || []).length === 0 ? (
          <div className="nc-empty" style={{ minHeight: 72 }}>Заготовок пока нет.</div>
        ) : (
          <div className="nc-row">
            {(settings.presets || []).map((item) => (
              <button
                key={item.name}
                type="button"
                className="nc-chip"
                onClick={() => {
                  setSettings({ ...item.settings, presets: settings.presets });
                  setTargetDraft((item.settings?.targets || []).join('\n'));
                }}
              >
                {item.name}
              </button>
            ))}
          </div>
        )}
        <input className="nc-input" style={{ marginTop: 10 }} value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Название заготовки" />
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head">
            <h2>Чаты и каналы</h2>
            <span className="nc-muted">Целей: {targetCount}</span>
          </div>
          <textarea className="nc-area" value={targetDraft} onChange={(event) => { setTargetDraft(event.target.value); setDirty(true); }} placeholder={'@groupname\nhttps://t.me/group\n-1001234567890'} />
          <p className="nc-hint">Форматы: @username, t.me/group, -100id. Папки те же, что в «Чаты и каналы».</p>
          <div className="nc-row" style={{ marginTop: 10 }}>
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => persist().then((saved) => customService.addParserTargets(id, (saved.settings.targets || []).join('\n'))), 'Ссылки добавлены в чаты')}>Сохранить в чаты</button>
            <CustomFileButton variant="ubt" accept=".csv,.xlsx,.xls,.txt" disabled={busy} onFile={(file) => runSafe(() => customService.importParserFile(id, file).then(applyPayload), 'Файл стал папкой чатов')}>Загрузить файл</CustomFileButton>
            <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты и каналы</Link>
          </div>
          <p className="nc-hint">Один файл — одна папка. CSV/Excel/txt со ссылками. Отсев «маленьких чатов» для своего файла не применяется.</p>
          <div style={{ marginTop: 12 }}>
            <div className="nc-row">
              <input className="nc-search" value={folderQuery} onChange={(event) => setFolderQuery(event.target.value)} placeholder="Поиск папки" />
            </div>
            {(folders || []).length === 0 ? <p className="nc-muted" style={{ marginTop: 8 }}>Папок пока нет — загрузите файл в «Чаты и каналы».</p> : (
              <div className="nc-list" style={{ marginTop: 8 }}>
                {folders.map((item) => (
                  <button key={item.id} type="button" className={`nc-item ${selectedFolders.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleFolder(item.id)}>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.count} чатов</span>
                    </div>
                    <span>{selectedFolders.has(item.id) ? 'цель' : 'выбрать'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Вступать перед сбором</strong>
              <span>Выбранные аккаунты сначала заходят в чаты, потом читают историю.</span>
            </div>
            <FeatureToggle compact title="" label="Вступать перед сбором" checked={Boolean(settings.do_join)} onChange={(value) => persistFlag({ do_join: value })} />
          </div>
          <div className="nc-setting nc-setting--muted">
            <div className="nc-setting-copy">
              <strong>Маркетплейс аккаунтов</strong>
              <span>Не подключаем. Свои сессии — в менеджере аккаунтов.</span>
            </div>
          </div>
        </div>

        <div className="nc-card">
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Окно по сообщениям</strong>
              <span>{settings.source === 'participants' ? 'Для списка участников окно не нужно.' : `Берём тех, кто писал за ${SINCE_OPTIONS.find((item) => item.value === Number(settings.since_hours))?.label || `${settings.since_hours}ч`}.`}</span>
            </div>
            <div className="nc-row">
              {SINCE_OPTIONS.map((item) => (
                <button key={item.value} type="button" className={`nc-chip ${Number(settings.since_hours) === item.value ? 'is-on' : ''}`} onClick={() => patch({ since_hours: item.value })}>{item.label}</button>
              ))}
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Лимит с чата</strong>
              <span>Не больше {settings.member_limit} человек из одной группы</span>
            </div>
            <Stepper value={settings.member_limit} min={1} max={10000} onChange={(value) => patch({ member_limit: value })} />
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Базовые фильтры</strong>
              <span>Отсекаем служебные и мёртвые аккаунты Telegram</span>
            </div>
            <div className="nc-checks">
              <UbtCheck checked={Boolean(settings.skip_bots)} onChange={(value) => persistFlag({ skip_bots: value })}>Пропустить ботов</UbtCheck>
              <UbtCheck checked={Boolean(settings.skip_deleted)} onChange={(value) => persistFlag({ skip_deleted: value })}>Пропустить удалённых</UbtCheck>
              <UbtCheck checked={Boolean(settings.skip_scam)} onChange={(value) => persistFlag({ skip_scam: value })}>Пропустить scam/fake</UbtCheck>
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Фильтры профиля</strong>
              <span>То, что Telegram отдаёт в карточке пользователя</span>
            </div>
            <div className="nc-checks">
              <UbtCheck checked={Boolean(settings.only_username)} onChange={(value) => persistFlag({ only_username: value })}>Только с username</UbtCheck>
              <UbtCheck checked={Boolean(settings.only_photo)} onChange={(value) => persistFlag({ only_photo: value })}>Только с фото</UbtCheck>
              <UbtCheck checked={Boolean(settings.only_premium)} onChange={(value) => persistFlag({ only_premium: value })}>Только Premium</UbtCheck>
              <UbtCheck checked={Boolean(settings.only_admins)} onChange={(value) => persistFlag({ only_admins: value })}>Только админы</UbtCheck>
              <UbtCheck checked={Boolean(settings.only_active_stories)} onChange={(value) => persistFlag({ only_active_stories: value })}>Только с активной историей</UbtCheck>
            </div>
          </div>
          <div className="nc-setting nc-setting--muted">
            <div className="nc-setting-copy">
              <strong>Пол, возраст, город</strong>
              <span>Не определяем. У Telegram нет надёжного источника для этого.</span>
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Задержки</strong>
              <span>Пауза между чатами и шаг между пользователями</span>
            </div>
            <div className="nc-row">
              <span className="nc-muted">чаты</span>
              <Stepper value={settings.delay_chat} min={0} max={120} onChange={(value) => patch({ delay_chat: value })} />
              <span className="nc-muted">с</span>
            </div>
            <div className="nc-row">
              <span className="nc-muted">люди</span>
              <Stepper value={settings.delay_user} min={0} max={30} onChange={(value) => patch({ delay_user: value })} />
              <span className="nc-muted">с</span>
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Ограничивать темп на аккаунт</strong>
              <span>После чата аккаунт уходит на паузу гуманизации, как у остальных модулей.</span>
            </div>
            <FeatureToggle compact title="" label="Ограничивать темп на аккаунт" checked={Boolean(settings.limit_rate)} onChange={(value) => persistFlag({ limit_rate: value })} />
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Ночной простой</strong>
              <span>С 21:30 до 07:00 по Москве парсер не идёт.</span>
            </div>
            <FeatureToggle compact title="" label="Ночной простой" checked={Boolean(settings.respect_night_hours)} onChange={(value) => persistFlag({ respect_night_hours: value })} />
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        {issues.length ? (
          <div className="nc-alert">
            <strong>Проблемы с конфигурацией</strong>
            {issues.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        <div className="nc-kpis" style={{ marginTop: 12 }}>
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{selectedFolders.size || selectedChats.size}</strong><span>Папки / чаты</span></div>
          <div className="nc-kpi"><strong>{settings.member_limit}</strong><span>Лимит с чата</span></div>
          <div className="nc-kpi"><strong>{data.summary?.users || 0}</strong><span>Собрано</span></div>
        </div>
        <div className="nc-logs" style={{ marginTop: 12 }}>
          {(activeJob?.logs || []).length === 0 ? 'Логи появятся после запуска. Хранятся 24 часа.' : (activeJob.logs || []).map((row, index) => (
            <div key={`${row.ts}-${index}`} className={row.level === 'error' ? 'nc-log-err' : ''}>{formatWhen(row.ts)} {row.message}</div>
          ))}
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
                await customService.runParserModule(id, { ...saved.settings, enabled: saved.enabled });
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
          <h2>Результаты парсинга</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=parser`}>Вся история</Link>
        </div>
        <div className="nc-row">
          <input className="nc-search" value={resultQuery} onChange={(event) => setResultQuery(event.target.value)} placeholder="Поиск результатов..." />
          <button type="button" className="acc-btn acc-btn--ghost" onClick={() => copyText(results.map((item) => item.link || (item.username ? `https://t.me/${item.username}` : '')).filter(Boolean).join('\n'))}>Скопировать ссылки</button>
          <button type="button" className="acc-btn acc-btn--ghost" onClick={() => copyText(results.map((item) => item.telegram_user_id).join('\n'))}>Скопировать ID</button>
          <button type="button" className="acc-btn acc-btn--ghost" onClick={exportCsv}>Экспорт CSV</button>
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.clearParserResults(id).then(applyPayload), 'Результаты очищены')}>Очистить</button>
        </div>
        {results.length === 0 ? (
          <div className="nc-empty" style={{ marginTop: 12 }}>Нет результатов. Они появятся после запуска.</div>
        ) : (
          <div className="nc-list" style={{ marginTop: 12 }}>
            {results.map((item) => (
              <div key={item.id} className="nc-item">
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.username ? `@${item.username}` : item.telegram_user_id} · {item.source_title || item.source_mode}</span>
                </div>
                <span>{formatWhen(item.last_message_at || item.created_at)}</span>
              </div>
            ))}
          </div>
        )}
        <p className="nc-muted" style={{ marginTop: 8 }}>Всего: {data.results_total || 0}</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Папки юзеров</h2>
          <span className="nc-muted">После задачи</span>
        </div>
        <p className="nc-hint">Каждый успешный запуск создаёт папку. Её можно выбрать целью в ЛС-рассылках и масспрайминге.</p>
        <UbtFolderPicker
          kind="users"
          readOnly
          folders={data.user_folders}
          emptyText="Папок ещё нет — они появятся после успешного парсинга."
        />
        <div className="nc-row" style={{ marginTop: 12 }}>
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'dm-broadcasts')}>ЛС-рассылки</Link>
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'masspriming')}>Масспрайминг</Link>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head">
            <h2>Статистика</h2>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'stats')}>Дашборд</Link>
          </div>
          <div className="nc-kpis">
            <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
            <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Чатов обработано</span></div>
            <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Ошибок</span></div>
            <div className="nc-kpi"><strong>{data.summary?.users || 0}</strong><span>Людей</span></div>
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
          {blockedAccountRows.length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Эти аккаунты не будут парсить, даже если попадут в пул.</p> : (
            <div className="nc-list" style={{ marginTop: 10 }}>
              {blockedAccountRows.map((item) => (
                <button key={item.id} type="button" className="nc-item" onClick={() => blockAccount(item.id)}>
                  <div><strong>{item.label}</strong><span>{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`}</span></div>
                  <span>×</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationParserPage;
