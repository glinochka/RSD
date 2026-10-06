import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { matchesPreset, toggleNumericId, ubtModulePath } from './customNav';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_min: 4, delay_max: 10 },
  rec: { delay_min: 8, delay_max: 25 },
  max: { delay_min: 20, delay_max: 45 },
};

const TTL_PERIODS = [
  { value: 86400, label: '1 день' },
  { value: 604800, label: '7 дней' },
  { value: 2678400, label: '1 месяц' },
];

const TTL_MODES = [
  { value: 'toggle', label: 'Вкл → выкл' },
  { value: 'enable', label: 'Только включить' },
  { value: 'disable', label: 'Только выключить' },
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

const CustomAutomationMassprimingPage = () => {
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
  const [blackAccountQuery, setBlackAccountQuery] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
    setTargetDraft((payload.settings?.targets || []).join('\n'));
  };

  const load = useCallback(async () => {
    const payload = await customService.getMassprimingModule(id);
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
  const recent = data?.summary?.recent || [];
  const targetCount = targetDraft.split('\n').filter((item) => item.trim()).length + selectedUserFolders.size;
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
    const result = await customService.saveMassprimingModule(id, payload);
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

  const toggleUserFolder = (folderId) => {
    patch({ user_folder_ids: toggleNumericId(settings.user_folder_ids, folderId) });
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
        <div className="nc-card"><p className="nc-muted">Загрузка масспрайминга...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Масспрайминг</h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <p className="nc-intro">Аккаунты не пишут в личку. Они открывают диалог, при необходимости добавляют контакт и переключают автоудаление сообщений. Цель видит системное уведомление «Ваш собеседник выключил автоудаление сообщений» и может заглянуть в профиль — вдруг это давний знакомый.</p>
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
              <strong>Выбрано для масспрайминга {chosenAccounts.length}</strong>
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
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveMassprimingPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
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
            <h2>Целевые контакты</h2>
            <span className="nc-muted">Целей: {targetCount}</span>
          </div>
          <textarea className="nc-area" value={targetDraft} onChange={(event) => { setTargetDraft(event.target.value); setDirty(true); }} placeholder={'@username\nhttps://t.me/username'} />
          <p className="nc-hint">Только публичные @username. Телефоны, инвайты и чаты пропускаются — модуль не импортирует контакты по номеру и не парсит участников.</p>
          <h3 className="nc-muted" style={{ marginTop: 16 }}>Папки из парсера юзеров</h3>
          <UbtFolderPicker kind="users" folders={data.user_folders} selectedIds={selectedUserFolders} onToggle={toggleUserFolder} />
          <div className="nc-setting nc-setting--muted" style={{ marginTop: 12 }}>
            <div className="nc-setting-copy">
              <strong>Сообщения в ЛС</strong>
              <span>Не отправляем. Ни приветствия, ни рассылки — только системное уведомление Telegram об автоудалении.</span>
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Добавлять в контакты</strong>
              <span>Как в клиенте: сохранить человека в адресную книгу перед переключением автоудаления.</span>
            </div>
            <FeatureToggle compact title="" label="Добавлять в контакты" checked={Boolean(settings.add_contact)} onChange={(value) => persistFlag({ add_contact: value })} />
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Автоудаление</strong>
              <span>По умолчанию включаем, чуть ждём и выключаем — именно выключение даёт пуш «собеседник выключил автоудаление».</span>
            </div>
            <div className="nc-row">
              {TTL_MODES.map((item) => (
                <button key={item.value} type="button" className={`nc-chip ${settings.ttl_mode === item.value ? 'is-on' : ''}`} onClick={() => patch({ ttl_mode: item.value })}>{item.label}</button>
              ))}
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Срок при включении</strong>
              <span>Telegram принимает сутки, неделю или месяц. Короткий срок выглядит естественнее.</span>
            </div>
            <div className="nc-row">
              {TTL_PERIODS.map((item) => (
                <button key={item.value} type="button" className={`nc-chip ${Number(settings.ttl_period) === item.value ? 'is-on' : ''}`} onClick={() => patch({ ttl_period: item.value })}>{item.label}</button>
              ))}
            </div>
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Задержка между контактами</strong>
              <span>Пауза после каждого успешного прайминга</span>
            </div>
            <div className="nc-row">
              <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.min) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.min)}>Мин</button>
              <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.rec) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.rec)}>Рек.</button>
              <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.max) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.max)}>Макс</button>
              <Stepper value={settings.delay_min} min={0} max={120} onChange={(value) => patch({ delay_min: value, delay_max: Math.max(value, settings.delay_max) })} />
              <span className="nc-muted">до</span>
              <Stepper value={settings.delay_max} min={settings.delay_min} max={180} onChange={(value) => patch({ delay_max: value })} />
              <span className="nc-muted">сек</span>
            </div>
          </div>
          <p className="nc-hint">FloodWait Telegram обрабатывается сам: короткие ждут на месте, длинные откладывают аккаунт.</p>
        </div>

        <div className="nc-card">
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Лимит на аккаунт за сутки (0 = без лимита)</strong>
              <span>{settings.max_per_account ? `${settings.max_per_account} контактов на аккаунт` : 'без лимита за сутки'}</span>
            </div>
            <Stepper value={settings.max_per_account} min={0} max={200} onChange={(value) => patch({ max_per_account: value })} />
          </div>
          <div className="nc-setting">
            <div className="nc-setting-copy">
              <strong>Не повторять недавно праймленных</strong>
              <span>Пропускаем пару аккаунт↔цель за {settings.skip_hours}ч</span>
            </div>
            <div className="nc-row">
              <Stepper value={settings.skip_hours} min={1} max={168} onChange={(value) => patch({ skip_hours: value, skip_seen: true })} />
              <FeatureToggle compact title="" label="Не повторять" checked={Boolean(settings.skip_seen)} onChange={(value) => persistFlag({ skip_seen: value })} />
            </div>
          </div>
          <div className="nc-setting nc-setting--muted">
            <div className="nc-setting-copy">
              <strong>Текст и медиа</strong>
              <span>Не шлём. Задача модуля — системный пуш и взгляд на профиль, не переписка.</span>
            </div>
          </div>
          <div className="nc-setting nc-setting--muted">
            <div className="nc-setting-copy">
              <strong>Сбор аудитории из групп</strong>
              <span>Не парсим участников. Работаем только по списку @username.</span>
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
            <span>После прохода — пауза 15–30 минут в очереди гуманизации, как у живого прогрева.</span>
          </div>
          <FeatureToggle compact title="" label="Ограничивать темп на аккаунт" checked={Boolean(settings.limit_rate)} onChange={(value) => persistFlag({ limit_rate: value })} />
        </div>
        <div className="nc-setting">
          <div className="nc-setting-copy">
            <strong>Действий в час на аккаунт</strong>
            <span>{settings.max_per_hour ? `Не больше ${settings.max_per_hour} праймингов за час. 0 — без почасового лимита.` : 'Почасовой лимит выключен'}</span>
          </div>
          <Stepper value={settings.max_per_hour || 0} min={0} max={80} onChange={(value) => patch({ max_per_hour: value })} />
        </div>
        <div className="nc-setting">
          <div className="nc-setting-copy">
            <strong>Ночной простой</strong>
            <span>С 21:30 до 07:00 по Москве прайминг не идёт.</span>
          </div>
          <FeatureToggle compact title="" label="Ночной простой" checked={Boolean(settings.respect_night_hours)} onChange={(value) => persistFlag({ respect_night_hours: value })} />
        </div>
        <div className="nc-setting">
          <div className="nc-setting-copy">
            <strong>Пропускать карантин прогрева</strong>
            <span>Аккаунты в статусе rest/warming не праймят, пока не отойдут от прогрева.</span>
          </div>
          <FeatureToggle compact title="" label="Пропускать карантин прогрева" checked={Boolean(settings.skip_quarantine)} onChange={(value) => persistFlag({ skip_quarantine: value })} />
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
                await customService.runMassprimingModule(id, { ...saved.settings, enabled: saved.enabled });
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
          <h2>История прайминга</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=masspriming`}>Вся история</Link>
        </div>
        {recent.length === 0 ? <p className="nc-muted">Пока пусто — появится после прогона.</p> : (
          <div className="nc-list">
            {recent.map((item) => (
              <div key={item.id} className="nc-item">
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.target} · {item.ttl_mode || 'ttl'} · {item.contact || 'контакт'}</span>
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
            <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Праймингов</span></div>
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
          {blockedAccountRows.length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Эти аккаунты не будут праймить, даже если попадут в пул.</p> : (
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

export default CustomAutomationMassprimingPage;
