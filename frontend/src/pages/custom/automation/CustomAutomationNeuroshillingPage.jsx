import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import CustomSelect from '../../../components/CustomSelect';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { folderOptions, matchesPreset, toggleNumericId, ubtModulePath } from './customNav';
import { DELAY_MAX_SECONDS } from './delayLimits';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_min: 4, delay_max: 10 },
  rec: { delay_min: 8, delay_max: 25 },
  max: { delay_min: 15, delay_max: 45 },
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

const CustomAutomationNeuroshillingPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [setup, setSetup] = useState('');
  const [reply, setReply] = useState('');
  const [topic, setTopic] = useState('');
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [targetTab, setTargetTab] = useState('links');
  const [links, setLinks] = useState('');
  const [linkKind, setLinkKind] = useState('auto');
  const [folderId, setFolderId] = useState('');
  const [dbQuery, setDbQuery] = useState('');
  const [blackQuery, setBlackQuery] = useState('');
  const [presetName, setPresetName] = useState('');
  const [check, setCheck] = useState(null);

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
    setSetup(payload.setup || '');
    setReply(payload.reply || '');
    if (payload.check) {
      setCheck(payload.check);
    }
  };

  const load = useCallback(async () => {
    const payload = await customService.getNeuroshillingModule(id);
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
  const selectedGroups = new Set(settings?.chat_ids || []);
  const selectedChannels = new Set(settings?.channel_ids || []);
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

  const dbChats = useMemo(() => {
    const items = data?.chats || [];
    const needle = dbQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (folderId && String(item.folder_id || '') !== String(folderId)) {
        return false;
      }
      if (targetTab === 'groups' && item.is_channel) {
        return false;
      }
      if (targetTab === 'channels' && !item.is_channel) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.title} ${item.invite_link || ''}`.toLowerCase().includes(needle);
    });
  }, [data, dbQuery, folderId, targetTab]);

  const chosenAccounts = (data?.accounts || []).filter((item) => selectedAccounts.has(item.id));
  const chosenGroups = (data?.chats || []).filter((item) => selectedGroups.has(item.id));
  const chosenChannels = (data?.chats || []).filter((item) => selectedChannels.has(item.id));
  const issues = data?.issues || [];
  const scenarioReady = Boolean(setup.trim() && reply.trim());
  const accountsReady = chosenAccounts.length >= 2;
  const busyAccounts = chosenAccounts.filter((item) => item.in_work);
  const delayLabel = settings ? `${settings.delay_min}–${settings.delay_max}с` : 'сразу';
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);
  const setupRef = useLiveRef(setup);
  const replyRef = useLiveRef(reply);

  const persist = async (next = {}) => {
    const payload = {
      ...settingsRef.current,
      ...next,
      enabled: next.enabled !== undefined ? next.enabled : enabledRef.current,
      setup: next.setup !== undefined ? next.setup : setupRef.current,
      reply: next.reply !== undefined ? next.reply : replyRef.current,
    };
    const result = await customService.saveNeuroshillingModule(id, payload);
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

  const toggleGroup = (chatId) => {
    const next = selectedGroups.has(chatId)
      ? settings.chat_ids.filter((item) => item !== chatId)
      : [...settings.chat_ids, chatId];
    patch({ chat_ids: next });
  };

  const toggleChannel = (chatId) => {
    const next = selectedChannels.has(chatId)
      ? settings.channel_ids.filter((item) => item !== chatId)
      : [...settings.channel_ids, chatId];
    patch({ channel_ids: next });
  };

  const toggleFolder = (folderId) => {
    patch({ folder_ids: toggleNumericId(settings.folder_ids, folderId) });
  };

  const applyPreset = (item) => {
    const next = { ...item.settings, presets: settings.presets };
    setSettings(next);
    const prompt = (data.prompts || []).find((row) => row.id === next.prompt_id);
    if (prompt) {
      setSetup(prompt.setup || '');
      setReply(prompt.reply || '');
    }
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка нейрошиллинга...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <div>
            <h2>Нейрошиллинг</h2>
            <p className="nc-intro">Два аккаунта пишут вопрос и ответ — как живое обсуждение. Случайно в группах и случайно в комментариях под постами.</p>
          </div>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Аккаунты <span className="nc-muted">Выбрано: {selectedAccounts.size}, нужно минимум 2</span></h2>
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'accounts')}>Выбрать аккаунты ›</Link>
        </div>
        <div className="nc-split">
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Доступные {accounts.length}</strong>
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
            {accounts.length === 0 ? <div className="nc-empty">Нет аккаунтов</div> : (
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
              <strong>Пара для диалога {chosenAccounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: [] })}>Удалить все</button>
            </div>
            {chosenAccounts.length === 0 ? <div className="nc-empty">Выберите минимум два аккаунта</div> : (
              <div className="nc-list">
                {chosenAccounts.map((item) => (
                  <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>
                        {item.daily_messages_sent ? `${item.daily_messages_sent} сегодня` : 'выбран'}
                      </span>
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
            <button key={item.name} type="button" className="nc-chip" onClick={() => applyPreset(item)}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Имя заготовки" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveNeuroshillingPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Конфигурация сценария</h2></div>
        <div className="nc-mode">
          <button type="button" className={settings.chat_shilling ? 'is-on' : ''} onClick={() => persistFlag({ chat_shilling: !settings.chat_shilling })}>В чатах</button>
          <button type="button" className={settings.post_shilling ? 'is-on' : ''} onClick={() => persistFlag({ post_shilling: !settings.post_shilling })}>В комментариях</button>
        </div>
        <p className="nc-muted" style={{ marginTop: 10 }}>
          Можно включить оба режима сразу. Пара сама выбирает случайную группу или свежий пост — это не сценарий с ролями и шагами, а живой вопрос-ответ двух аккаунтов.
        </p>
        <div className="nc-split" style={{ marginTop: 14 }}>
          <div>
            <div className="nc-row">
              <span className="nc-muted">Тема обсуждения</span>
              <button
                type="button"
                className="nc-chip"
                disabled={busy}
                onClick={() => runSafe(async () => {
                  if (!topic.trim()) {
                    throw new Error('Опишите тему, чтобы сгенерировать реплики');
                  }
                  const payload = await customService.generateNeuroshillingLines(id, topic);
                  applyPayload(payload);
                  return payload;
                }, 'Реплики сгенерированы')}
              >
                Сгенерировать через ИИ
              </button>
            </div>
            <textarea className="nc-area" style={{ marginTop: 8 }} value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Например: обсудите удобный сервис X, без ссылок и лозунгов" />
          </div>
          <div>
            <p className="nc-muted">Ссылки и медиа в реплики не ставим: публичный текст чистится, картинки не отправляются.</p>
            <p className="nc-note">Реплики не читают историю чата. Это всегда короткая пара: вопрос инициатора и ответ второго аккаунта.</p>
          </div>
        </div>
        <div className="nc-split" style={{ marginTop: 14 }}>
          <div>
            <span className="nc-muted">Вопрос инициатора</span>
            <textarea className="nc-area" style={{ marginTop: 8 }} value={setup} onChange={(event) => { setSetup(event.target.value); setDirty(true); }} placeholder="Живой вопрос от первого аккаунта" />
          </div>
          <div>
            <span className="nc-muted">Ответ второго аккаунта</span>
            <textarea className="nc-area" style={{ marginTop: 8 }} value={reply} onChange={(event) => { setReply(event.target.value); setDirty(true); }} placeholder="Спокойный ответ знакомого, без рекламы" />
          </div>
        </div>
        <div className="nc-prompts" style={{ marginTop: 12 }}>
          {(data.prompts || []).map((prompt) => (
            <button
              key={prompt.id}
              type="button"
              className={`nc-prompt ${settings.prompt_id === prompt.id || (!settings.prompt_id && prompt.is_active) ? 'is-on' : ''}`}
              onClick={() => { patch({ prompt_id: prompt.id }); setSetup(prompt.setup || ''); setReply(prompt.reply || ''); }}
            >
              <strong>{prompt.name}</strong>
              <div className="nc-muted">{prompt.is_system ? 'Системный' : 'Мой промпт'}</div>
            </button>
          ))}
          <Link className="nc-prompt" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)}>Все промпты</Link>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Поведение пары</h2>
          <div className="nc-row">
            <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.min) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.min)}>Мин</button>
            <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.rec) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.rec)}>Рекомендуемые</button>
            <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.max) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.max)}>Макс</button>
          </div>
        </div>
        <div className="nc-split">
          <FeatureToggle compact title="Уникальные сообщения" description="Каждый запуск слегка варьирует вопрос и ответ, чтобы пары не копировали друг друга." checked={Boolean(settings.unique_messages)} onChange={(value) => persistFlag({ unique_messages: value })} />
          <FeatureToggle compact title="Пропускать свежие аккаунты" description="Новые аккаунты в осторожной стадии не идут в шиллинг, пока не прогреются." checked={Boolean(settings.skip_fresh)} onChange={(value) => persistFlag({ skip_fresh: value })} />
        </div>
        <div className="nc-row" style={{ marginTop: 12 }}>
          <span className="nc-muted">Пауза между репликами</span>
          <Stepper value={settings.delay_min} min={0} max={DELAY_MAX_SECONDS} onChange={(value) => patch({ delay_min: value, delay_max: Math.max(value, settings.delay_max) })} />
          <span className="nc-muted">до</span>
          <Stepper value={settings.delay_max} min={settings.delay_min} max={DELAY_MAX_SECONDS} onChange={(value) => patch({ delay_max: value })} />
          <span className="nc-muted">с</span>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Настройка кампании</h2>
          <span className="nc-muted">{selectedFolders.size} пап. · {chosenGroups.length} групп · {chosenChannels.length} каналов</span>
        </div>
        <div className="nc-split">
          <div>
            <span className="nc-muted">Цели</span>
            <p className="nc-hint">@username, t.me/chan — Enter; можно списком. Пустой список = все доступные цели, куда аккаунты уже могут писать.</p>
            <div className="nc-row" style={{ marginTop: 8 }}>
              <button type="button" className={`nc-chip ${targetTab === 'links' ? 'is-on' : ''}`} onClick={() => setTargetTab('links')}>Ссылки</button>
              <button type="button" className={`nc-chip ${targetTab === 'folder' ? 'is-on' : ''}`} onClick={() => setTargetTab('folder')}>Папки</button>
              <button type="button" className={`nc-chip ${targetTab === 'groups' ? 'is-on' : ''}`} onClick={() => setTargetTab('groups')}>Группы из папок</button>
              <button type="button" className={`nc-chip ${targetTab === 'channels' ? 'is-on' : ''}`} onClick={() => setTargetTab('channels')}>Каналы из папок</button>
              <button type="button" className={`nc-chip ${targetTab === 'jobs' ? 'is-on' : ''}`} onClick={() => setTargetTab('jobs')}>Прошлые запуски</button>
            </div>
            {targetTab === 'links' ? (
              <div style={{ marginTop: 10 }}>
                <textarea className="nc-area" value={links} onChange={(event) => setLinks(event.target.value)} placeholder="@chat или https://t.me/channel" />
                <div className="nc-row" style={{ marginTop: 8 }}>
                  <CustomSelect
                    className="nc-select"
                    value={linkKind}
                    options={[
                      { value: 'auto', label: 'Авто: группа или канал' },
                      { value: 'group', label: 'Как группу' },
                      { value: 'channel', label: 'Как канал' },
                    ]}
                    onChange={(event) => setLinkKind(event.target.value)}
                  />
                  <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addNeuroshillingTargets(id, links, linkKind).then((payload) => { applyPayload(payload); setLinks(''); if (payload.add_errors?.length) { setError(payload.add_errors.join('; ')); } return payload; }), 'Цели добавлены')}>+ Добавить</button>
                  <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты и каналы</Link>
                </div>
              </div>
            ) : null}
            {targetTab === 'folder' ? (
              <UbtFolderPicker folders={data.folders} selectedIds={selectedFolders} onToggle={toggleFolder} />
            ) : null}
            {targetTab === 'jobs' ? (
              <div className="nc-list" style={{ marginTop: 10 }}>
                {jobs.length === 0 ? <div className="nc-empty">Прошлых запусков нет</div> : jobs.map((item) => (
                  <button key={item.id} type="button" className="nc-item" onClick={() => patch({ chat_ids: item.params?.chat_ids || settings.chat_ids, channel_ids: item.params?.channel_ids || settings.channel_ids, account_ids: item.params?.account_ids || settings.account_ids })}>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{STATUS_LABELS[item.status] || item.status} · {formatWhen(item.created_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : null}
            {targetTab === 'groups' || targetTab === 'channels' ? (
              <div style={{ marginTop: 10 }}>
                <div className="nc-row">
                  <CustomSelect
                    className="nc-select"
                    value={String(folderId || '')}
                    options={folderOptions(data.folders)}
                    onChange={(event) => setFolderId(event.target.value)}
                  />
                  <input className="nc-search" value={dbQuery} onChange={(event) => setDbQuery(event.target.value)} placeholder="Поиск" />
                  <button
                    type="button"
                    className="acc-btn acc-btn--ghost"
                    onClick={() => patch(targetTab === 'channels'
                      ? { channel_ids: dbChats.filter((item) => item.is_channel).map((item) => item.id) }
                      : { chat_ids: dbChats.filter((item) => !item.is_channel).map((item) => item.id) })}
                  >
                    Добавить найденные
                  </button>
                </div>
                <div className="nc-list" style={{ marginTop: 8 }}>
                  {dbChats.map((item) => {
                    const on = item.is_channel ? selectedChannels.has(item.id) : selectedGroups.has(item.id);
                    return (
                      <button key={item.id} type="button" className={`nc-item ${on ? 'is-on' : ''}`} onClick={() => (item.is_channel ? toggleChannel(item.id) : toggleGroup(item.id))}>
                        <div>
                          <strong>{item.title}</strong>
                          <span>{item.is_channel ? 'канал' : 'группа'} · {item.join_status}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
            {chosenGroups.length || chosenChannels.length ? (
              <div className="nc-list" style={{ marginTop: 10 }}>
                {chosenGroups.map((item) => (
                  <button key={`g-${item.id}`} type="button" className="nc-item is-on" onClick={() => toggleGroup(item.id)}>
                    <div><strong>{item.title}</strong><span>группа</span></div>
                    <span>×</span>
                  </button>
                ))}
                {chosenChannels.map((item) => (
                  <button key={`c-${item.id}`} type="button" className="nc-item is-on" onClick={() => toggleChannel(item.id)}>
                    <div><strong>{item.title}</strong><span>канал</span></div>
                    <span>×</span>
                  </button>
                ))}
              </div>
            ) : <p className="nc-muted" style={{ marginTop: 10 }}>0 целей — модуль сам берёт доступные группы и каналы.</p>}
          </div>
          <div>
            <span className="nc-muted">Как часто</span>
            <p className="nc-note">В группе — не чаще раза в московский день, и только после ~100 сообщений или 7 тихих дней. Под постом — вместе с нейрокомментингом, если комментарии открыты. Забаненную пару пропускаем и берём другую.</p>
            <p className="nc-note">
              Ответы реальным людям в чате — это <Link to={ubtModulePath(id, 'neurochatting')}>Нейрочаттинг</Link>. Входящие личные обрабатывает перехват заявок. Здесь аккаунты только разыгрывают свою пару реплик.
            </p>
            <p className="nc-muted" style={{ marginTop: 10 }}>Сухой прогон ничего не отправляет. Живой тест — в <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_TEST(id)}>лаборатории</Link>.</p>
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск кампании</h2></div>
        <div className="nc-gate">
          <span className={accountsReady ? 'is-ok' : 'is-bad'}>Аккаунты {selectedAccounts.size}/2</span>
          <span className={scenarioReady ? 'is-ok' : 'is-bad'}>Сценарий {scenarioReady ? 'готов' : 'не заполнен'}</span>
          <span className="is-ok">Цели {chosenGroups.length + chosenChannels.length || 'все доступные'}</span>
        </div>
        {issues.length ? (
          <div className="nc-alert" style={{ marginTop: 12 }}>
            <strong>Черновик сценария — не применён</strong>
            {issues.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        <div className="nc-card nc-card--soft">
          <div className="nc-card-head">
            <div>
              <h2>Сухой прогон</h2>
              <p className="nc-muted">Проверит аккаунты, роли и цели. В Telegram ничего не уйдёт.</p>
            </div>
            <button
              type="button"
              className="acc-btn acc-btn--primary"
              disabled={busy}
              onClick={() => runSafe(async () => {
                const saved = await persist();
                const payload = await customService.checkNeuroshillingModule(id, {
                  ...saved.settings,
                  enabled: saved.enabled,
                  setup: saved.setup,
                  reply: saved.reply,
                });
                applyPayload(payload);
                return payload;
              }, 'Проверка выполнена')}
            >
              Проверить
            </button>
          </div>
          <div className="nc-kpis nc-kpis--4">
            <div className="nc-kpi"><strong>{check?.accounts ?? selectedAccounts.size}</strong><span>Аккаунты</span></div>
            <div className="nc-kpi"><strong>{(check ? check.groups + check.channels : chosenGroups.length + chosenChannels.length) || 'все'}</strong><span>Цели</span></div>
            <div className="nc-kpi"><strong>{check?.replies ?? (scenarioReady ? 2 : 0)}</strong><span>Реплик</span></div>
            <div className="nc-kpi"><strong>{delayLabel}</strong><span>Диалог займёт</span></div>
          </div>
        </div>
        {busyAccounts.length ? (
          <p className="nc-note">Часть выбранных аккаунтов уже в работе сегодня — для нового запуска выберите другие или включите «Скрыть в работе».</p>
        ) : null}
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
                await customService.runNeuroshillingModule(id, {
                  ...saved.settings,
                  enabled: saved.enabled,
                  setup: saved.setup,
                  reply: saved.reply,
                });
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
          <h2>История</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=shilling`}>Открыть полную историю →</Link>
        </div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Успешно</span></div>
          <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Ошибки</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success_pct || 0}%</strong><span>Процент успеха</span></div>
        </div>
        <p className="nc-muted" style={{ marginTop: 8 }}>В чатах: {data.summary?.chats || 0} · в комментариях: {data.summary?.posts || 0}</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Чёрный список</h2></div>
        <p className="nc-muted">Чаты, в которые шиллинг не пишет. Модуль пополняет список при банах и отказах.</p>
        <div className="nc-row" style={{ marginTop: 10 }}>
          <input className="nc-search" value={blackQuery} onChange={(event) => setBlackQuery(event.target.value)} placeholder="@chat, ссылка t.me — можно списком" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.blackboxNeuroshillingChat(id, { query: blackQuery }).then((payload) => { applyPayload(payload); setBlackQuery(''); return payload; }), 'Чат в чёрном списке')}>+ Добавить</button>
        </div>
        {(data.blacklist || []).length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Чёрный список пуст. Проблемные чаты попадут сюда автоматически или добавьте их вручную.</p> : (
          <div className="nc-list" style={{ marginTop: 10 }}>
            {(data.blacklist || []).map((item) => (
              <div key={item.id} className="nc-item">
                <div><strong>{item.title}</strong><span>{item.reason || 'вручную'}</span></div>
                <span>{formatWhen(item.black_boxed_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationNeuroshillingPage;
