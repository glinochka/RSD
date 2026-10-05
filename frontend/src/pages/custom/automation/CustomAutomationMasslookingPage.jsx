import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { ubtModulePath } from './customNav';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_min: 1, delay_max: 3 },
  rec: { delay_min: 2, delay_max: 6 },
  max: { delay_min: 4, delay_max: 12 },
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

const Stepper = ({ value, min = 0, max = 999, onChange }) => (
  <div className="nc-step">
    <button type="button" onClick={() => onChange(Math.max(min, Number(value || 0) - 1))}>−</button>
    <strong>{value}</strong>
    <button type="button" onClick={() => onChange(Math.min(max, Number(value || 0) + 1))}>+</button>
  </div>
);

const CustomAutomationMasslookingPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [folderId, setFolderId] = useState('');
  const [dbQuery, setDbQuery] = useState('');
  const [presetName, setPresetName] = useState('');
  const [targetDraft, setTargetDraft] = useState('');
  const [blackAccountQuery, setBlackAccountQuery] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
    setTargetDraft((payload.settings?.targets || []).join('\n'));
  };

  const load = useCallback(async () => {
    const payload = await customService.getMasslookingModule(id);
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

  const patch = (partial) => setSettings((prev) => ({ ...prev, ...partial }));
  const selectedAccounts = new Set(settings?.account_ids || []);
  const selectedChats = new Set(settings?.chat_ids || []);
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
      if (roleFilter && roleFilter !== 'all' && !(item.roles || []).includes(roleFilter)) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.label} ${item.username || ''} ${item.phone_number || ''} ${item.id}`.toLowerCase().includes(needle);
    });
  }, [data, accountQuery, roleFilter, settings, blockedAccounts]);

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
  const blockedAccountRows = (data?.accounts || []).filter((item) => blockedAccounts.has(item.id));
  const issues = data?.issues || [];
  const recent = data?.summary?.recent || [];
  const targetCount = targetDraft.split('\n').filter((item) => item.trim()).length + selectedChats.size;

  const persist = async (next = {}) => {
    const payload = {
      ...settings,
      enabled,
      ...next,
      targets: (next.targets !== undefined ? next.targets : targetDraft.split('\n').map((item) => item.trim()).filter(Boolean)),
    };
    const result = await customService.saveMasslookingModule(id, payload);
    applyPayload(result);
    return result;
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

  const toggleChat = (chatId) => {
    const next = selectedChats.has(chatId)
      ? settings.chat_ids.filter((item) => item !== chatId)
      : [...settings.chat_ids, chatId];
    patch({ chat_ids: next });
  };

  const blockAccount = (accountId) => {
    patch({
      blacklisted_account_ids: blockedAccounts.has(accountId)
        ? settings.blacklisted_account_ids.filter((item) => item !== accountId)
        : [...(settings.blacklisted_account_ids || []), accountId],
      account_ids: settings.account_ids.filter((item) => item !== accountId),
    });
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка масслукинга...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Масслукинг</h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <p className="nc-intro">Массовый просмотр историй каналов и пользователей от лица ваших аккаунтов. Тот же жест, что в живой сессии: открыть сторис и отметить просмотренным.</p>
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
              <select className="nc-select" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
                <option value="all">Все роли</option>
                <option value="neurocommenting">Нейрокомментинг</option>
                <option value="lead_intercept">Перехват</option>
                <option value="shilling">Шиллинг</option>
              </select>
            </div>
            <div className="nc-row">
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: accounts.filter((item) => item.eligible).map((item) => item.id) })}>Добавить все</button>
              <label className="check"><input type="checkbox" checked={Boolean(settings.require_proxy)} onChange={(event) => patch({ require_proxy: event.target.checked })} /> Рабочие прокси</label>
              <label className="check"><input type="checkbox" checked={Boolean(settings.hide_in_work)} onChange={(event) => patch({ hide_in_work: event.target.checked })} /> Скрыть в работе</label>
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
              <strong>Выбрано для масслукинга {chosenAccounts.length}</strong>
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
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveMasslookingPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
        </div>
        {(settings.presets || []).length === 0 ? (
          <div className="nc-empty" style={{ minHeight: 72 }}>Заготовок пока нет. Выберите аккаунты, настройте запуск и нажмите «Сохранить заготовку».</div>
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
            <h2>Пользователи и чаты</h2>
            <span className="nc-muted">Целей: {targetCount}</span>
          </div>
          <textarea className="nc-area" value={targetDraft} onChange={(event) => setTargetDraft(event.target.value)} placeholder={'@username\nhttps://t.me/channel\nhttps://t.me/chat'} />
          <p className="nc-hint">Юзеры — цель; каналы/чаты с публичным @username. Приватные инвайты без username пропускаются: у них нет публичных историй.</p>
          <div style={{ marginTop: 12 }}>
            <FeatureToggle compact title="Смотреть ленту историй аккаунта" description="Как в живой сессии: открываем сторис из ленты подписок, даже если список целей пуст." checked={Boolean(settings.view_feed)} onChange={(value) => patch({ view_feed: value })} />
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="nc-row">
              <select className="nc-select" value={folderId} onChange={(event) => setFolderId(event.target.value)}>
                <option value="">Все папки</option>
                {(data.folders || []).map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
              </select>
              <input className="nc-search" value={dbQuery} onChange={(event) => setDbQuery(event.target.value)} placeholder="Поиск канала" />
              <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>База</Link>
            </div>
            <div className="nc-list" style={{ marginTop: 8 }}>
              {dbChats.slice(0, 40).map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.invite_link || item.chat_type || ''}</span>
                  </div>
                </button>
              ))}
            </div>
            {chosenChats.length ? (
              <p className="nc-muted" style={{ marginTop: 8 }}>Из папок: {chosenChats.map((item) => item.title).join(', ')}</p>
            ) : null}
          </div>
          <div className="nc-setting nc-setting--muted" style={{ marginTop: 8 }}>
            <div className="nc-setting-copy">
              <strong>Из групп брать по списку участников</strong>
              <span>Не собираем аудиторию из участников. Смотрим только указанные цели и ленту.</span>
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Задержка между переходами</strong>
              <span>Пауза после каждого просмотренного источника</span>
            </div>
            <div className="nc-row">
              <button type="button" className="nc-chip" onClick={() => patch(DELAY_PRESETS.min)}>Мин</button>
              <button type="button" className="nc-chip is-on" onClick={() => patch(DELAY_PRESETS.rec)}>Рек.</button>
              <Stepper value={settings.delay_min} min={0} max={120} onChange={(value) => patch({ delay_min: value, delay_max: Math.max(value, settings.delay_max) })} />
              <span className="nc-muted">до</span>
              <Stepper value={settings.delay_max} min={settings.delay_min} max={180} onChange={(value) => patch({ delay_max: value })} />
              <span className="nc-muted">сек</span>
            </div>
          </div>
          <p className="nc-hint">FloodWait Telegram обрабатывается сам: короткие ждут на месте, длинные откладывают аккаунт. Отдельный карантин после N флудов не нужен.</p>
        </div>

        <div className="nc-card">
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Сколько историй просматривать</strong>
              <span>{settings.stories_limit ? `${settings.stories_limit} источников за проход` : 'без ограничений'}</span>
            </div>
            <Stepper value={settings.stories_limit} min={0} max={500} onChange={(value) => patch({ stories_limit: value })} />
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Лимит просмотров на аккаунт (0 = без лимита)</strong>
              <span>{settings.max_per_account ? `${settings.max_per_account} просмотров на аккаунт` : 'без лимита за сутки'}</span>
            </div>
            <Stepper value={settings.max_per_account} min={0} max={500} onChange={(value) => patch({ max_per_account: value })} />
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Не смотреть повторно</strong>
              <span>Пропускаем просмотренные за {settings.skip_hours}ч</span>
            </div>
            <div className="nc-row">
              <Stepper value={settings.skip_hours} min={1} max={168} onChange={(value) => patch({ skip_hours: value, skip_seen: true })} />
              <FeatureToggle compact title="" checked={Boolean(settings.skip_seen)} onChange={(value) => patch({ skip_seen: value })} />
            </div>
          </div>
          <div className="nc-setting nc-setting--muted">
            <div className="nc-setting-copy">
              <strong>Лайк на истории</strong>
              <span>Не ставим. Только просмотр — без сердечка и без ухода в личку.</span>
            </div>
          </div>
          <div className="nc-setting nc-setting--muted">
            <div className="nc-setting-copy">
              <strong>Реакции на истории</strong>
              <span>Случайные эмодзи не отправляем. Это уже другой жест, не масслукинг.</span>
            </div>
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Особые настройки</h2>
          <span className="nc-muted">Поведенческие твики — по умолчанию включены мягко</span>
        </div>
        <div className="nc-setting">
          <div className="nc-setting-copy">
            <strong>Ограничивать темп на аккаунт</strong>
            <span>После просмотров — пауза 15–30 минут в очереди гуманизации, как у живого прогрева.</span>
          </div>
          <FeatureToggle compact title="" checked={Boolean(settings.limit_rate)} onChange={(value) => patch({ limit_rate: value })} />
        </div>
        <div className="nc-setting">
          <div className="nc-setting-copy">
            <strong>Действий в час на аккаунт</strong>
            <span>{settings.max_per_hour ? `Не больше ${settings.max_per_hour} просмотров за час. 0 — без почасового лимита.` : 'Почасовой лимит выключен'}</span>
          </div>
          <Stepper value={settings.max_per_hour || 0} min={0} max={200} onChange={(value) => patch({ max_per_hour: value })} />
        </div>
        <div className="nc-setting">
          <div className="nc-setting-copy">
            <strong>Ночной простой</strong>
            <span>С 21:30 до 07:00 по Москве просмотры не идут.</span>
          </div>
          <FeatureToggle compact title="" checked={Boolean(settings.respect_night_hours)} onChange={(value) => patch({ respect_night_hours: value })} />
        </div>
        <div className="nc-setting nc-setting--muted">
          <div className="nc-setting-copy">
            <strong>Прогрев новых аккаунтов</strong>
            <span>Общий разгон живёт в подразделе «Прогрев», здесь его не дублируем.</span>
          </div>
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'warmup')}>Прогрев</Link>
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
          <div className="nc-kpi"><strong>{targetCount}</strong><span>Цели</span></div>
          <div className="nc-kpi"><strong>{settings.delay_max}s</strong><span>Макс. пауза</span></div>
          <div className="nc-kpi"><strong>{settings.max_per_account || '∞'}</strong><span>Лимит на аккаунт</span></div>
        </div>
        <div className="nc-logs" style={{ marginTop: 12 }}>
          {(activeJob?.logs || []).length === 0 ? 'Логи появятся после запуска. Хранятся 24 часа.' : (activeJob.logs || []).map((row, index) => (
            <div key={`${row.ts}-${index}`} className={row.level === 'error' ? 'nc-log-err' : ''}>{formatWhen(row.ts)} {row.message}</div>
          ))}
        </div>
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
              disabled={busy}
              onClick={() => runSafe(async () => {
                const saved = await persist();
                await customService.runMasslookingModule(id, { ...saved.settings, enabled: true });
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
          <h2>История просмотров</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=masslooking`}>Вся история</Link>
        </div>
        {recent.length === 0 ? <p className="nc-muted">Пока пусто — появится после прогона.</p> : (
          <div className="nc-list">
            {recent.map((item) => (
              <div key={item.id} className="nc-item">
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.source === 'feed' ? 'лента' : item.target} · {item.stories || 0} ист.</span>
                </div>
                <span>{formatWhen(item.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head">
            <h2>Статистика</h2>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'stats')}>Дашборд</Link>
          </div>
          <div className="nc-kpis">
            <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
            <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Просмотров</span></div>
            <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Ошибок</span></div>
            <div className="nc-kpi"><strong>{data.summary?.success_pct || 0}%</strong><span>Успешных</span></div>
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
          {blockedAccountRows.length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Эти аккаунты не будут смотреть истории, даже если попадут в пул.</p> : (
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

export default CustomAutomationMasslookingPage;
