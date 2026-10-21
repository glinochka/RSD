import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import CustomSelect from '../../../components/CustomSelect';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { toggleNumericId, ubtModulePath } from './customNav';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const EMPTY = {
  account_ids: [],
  channel_title: 'Заметки',
  channel_about: 'Личные заметки о работе.',
  style: 'живой разговорный, от первого лица, без канцелярита',
  posts_per_day: 2,
  themes: ['expert', 'case', 'blog', 'reflection', 'infographic'],
  product_name: '',
  product_url: '',
  prompt: '',
  text_provider: 'deepseek',
  text_model: 'deepseek-flash',
  image_provider: '',
  image_model: '',
  require_proxy: false,
  hide_in_work: false,
};

const THEME_FALLBACK = [
  { id: 'expert', label: 'Эксперт' },
  { id: 'case', label: 'Кейс' },
  { id: 'blog', label: 'Блог' },
  { id: 'reflection', label: 'Размышление' },
  { id: 'infographic', label: 'Инфографика' },
];

const TEXT_FALLBACK = [
  { id: 'chatgpt', label: 'ChatGPT', models: [{ id: 'gpt-6-luna', label: 'GPT-6 Luna' }, { id: 'gpt-6-sol', label: 'GPT-6 Sol' }, { id: 'gpt-6-astra', label: 'GPT-6 Astra' }], images: true },
  { id: 'claude', label: 'Claude', models: [{ id: 'claude-sonnet-5-5', label: 'Sonnet 5.5' }, { id: 'claude-haiku-5-5', label: 'Haiku 5.5' }, { id: 'claude-opus-5-5', label: 'Opus 5.5' }], images: false },
  { id: 'grok', label: 'Grok', models: [{ id: 'grok-4.7', label: 'Grok 4.7' }, { id: 'grok-4.3', label: 'Grok 4.3' }], images: true },
  { id: 'deepseek', label: 'DeepSeek', models: [{ id: 'deepseek-flash', label: 'DeepSeek Flash' }, { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' }], images: false },
];

const IMAGE_FALLBACK = [
  { id: 'chatgpt', label: 'ChatGPT', models: [{ id: 'gpt-image-2.5-flare', label: 'GPT Image 2.5 Flare' }] },
  { id: 'grok', label: 'Grok', models: [{ id: 'grok-imagine-image-2.0', label: 'Grok Imagine 2.0' }] },
];

const formatWhen = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const modelOptions = (items) => (items || []).map((item) => ({
  value: item.id || item,
  label: item.label || item.id || item,
}));

const CustomAutomationNeuroblogPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(EMPTY);
  const [enabled, setEnabled] = useState(false);
  const [textKey, setTextKey] = useState('');
  const [imageKey, setImageKey] = useState('');
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [searchLocked, setSearchLocked] = useState(true);
  const [avatarFileName, setAvatarFileName] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setEnabled(Boolean(payload.enabled));
    setSettings({ ...EMPTY, ...(payload.settings || {}) });
    setTextKey('');
    setImageKey('');
  };

  const load = useCallback(async () => {
    const payload = await customService.getNeuroblogModule(id);
    applyPayload(payload);
    setError(null);
  }, [id]);

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Не удалось открыть нейроблог'));
  }, [load]);

  const dirtyRef = useLiveRef(dirty);
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      if (dirtyRef.current) {
        return;
      }
      load().catch(() => {});
    }, 8000);
    return () => window.clearInterval(timer);
  }, [enabled, load, dirtyRef]);

  const patch = (partial) => {
    setSettings((prev) => ({ ...prev, ...partial }));
    setDirty(true);
  };
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);
  const textKeyRef = useLiveRef(textKey);
  const imageKeyRef = useLiveRef(imageKey);

  const persist = async (next = {}) => {
    const current = { ...settingsRef.current, enabled: enabledRef.current, ...next };
    const payload = {
      enabled: current.enabled,
      settings: {
        account_ids: current.account_ids,
        channel_title: current.channel_title,
        channel_about: current.channel_about,
        style: current.style,
        posts_per_day: Number(current.posts_per_day) || 1,
        themes: current.themes,
        product_name: current.product_name,
        product_url: current.product_url,
        prompt: current.prompt,
        text_provider: current.text_provider,
        text_model: current.text_model,
        image_provider: current.image_provider,
        image_model: current.image_model,
        require_proxy: Boolean(current.require_proxy),
        hide_in_work: Boolean(current.hide_in_work),
      },
    };
    if (textKeyRef.current.trim()) {
      payload.settings.text_api_key = textKeyRef.current.trim();
    }
    if (imageKeyRef.current.trim()) {
      payload.settings.image_api_key = imageKeyRef.current.trim();
    }
    const result = await customService.saveNeuroblogModule(id, payload);
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

  const selectedAccounts = new Set(settings?.account_ids || []);
  const textProviders = data?.text_providers?.length ? data.text_providers : TEXT_FALLBACK;
  const imageProviders = data?.image_providers?.length ? data.image_providers : IMAGE_FALLBACK;
  const themes = data?.themes?.length ? data.themes : THEME_FALLBACK;
  const activeText = textProviders.find((item) => item.id === settings.text_provider) || textProviders[0];
  const activeImage = imageProviders.find((item) => item.id === settings.image_provider) || null;
  const issues = data?.issues || [];
  const notices = data?.notices || [];

  const accounts = useMemo(() => {
    const items = data?.accounts || [];
    const raw = accountQuery.trim().toLowerCase();
    const needle = /.+@.+\./.test(raw) ? '' : raw;
    return items.filter((item) => {
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
  }, [data, accountQuery, settings]);

  const chosenAccounts = (data?.accounts || []).filter((item) => selectedAccounts.has(item.id));
  const themeLabel = (themeId) => themes.find((item) => item.id === themeId)?.label || themeId;

  const toggleAccount = (accountId) => {
    patch({ account_ids: toggleNumericId(settings.account_ids, accountId) });
  };

  const toggleTheme = (themeId) => {
    const ids = settings.themes || [];
    const next = ids.includes(themeId) ? ids.filter((item) => item !== themeId) : [...ids, themeId];
    patch({ themes: next.length ? next : ids });
  };

  const setTextProvider = (providerId) => {
    const spec = textProviders.find((item) => item.id === providerId) || textProviders[0];
    const nextModel = (spec.models || []).some((item) => item.id === settings.text_model)
      ? settings.text_model
      : spec.models?.[0]?.id;
    patch({ text_provider: spec.id, text_model: nextModel });
  };

  const setImageProvider = (providerId) => {
    if (!providerId) {
      patch({ image_provider: '', image_model: '' });
      return;
    }
    const spec = imageProviders.find((item) => item.id === providerId);
    patch({
      image_provider: providerId,
      image_model: spec?.models?.[0]?.id || '',
    });
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка нейроблога...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Выбор аккаунтов <span className="nc-muted">{selectedAccounts.size} выбрано</span></h2>
          <FeatureToggle
            compact
            title={enabled ? 'Модуль включён' : 'Модуль выключен'}
            checked={enabled}
            onChange={(value) => {
              setEnabled(value);
              persist({ enabled: value });
            }}
          />
        </div>
        <div className="nc-split">
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Доступные аккаунты {accounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => load()}>Обновить</button>
            </div>
            <div className="nc-row">
              <input tabIndex={-1} aria-hidden="true" autoComplete="username" style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }} />
              <input tabIndex={-1} aria-hidden="true" type="password" autoComplete="current-password" style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }} />
              <input
                className="nc-search"
                type="search"
                name="ubt-account-filter"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                data-lpignore="true"
                data-1p-ignore="true"
                readOnly={searchLocked}
                value={/.+@.+\./.test(accountQuery.trim()) ? '' : accountQuery}
                onFocus={() => setSearchLocked(false)}
                onChange={(event) => setAccountQuery(event.target.value)}
                placeholder="Поиск по ID, телефону, username..."
              />
            </div>
            <div className="nc-row">
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: accounts.filter((item) => item.eligible).map((item) => item.id) })}>Добавить все</button>
              <UbtCheck checked={Boolean(settings.require_proxy)} onChange={(value) => persistFlag({ require_proxy: value })}>Рабочие прокси</UbtCheck>
              <UbtCheck checked={Boolean(settings.hide_in_work)} onChange={(value) => persistFlag({ hide_in_work: value })}>Скрыть в работе</UbtCheck>
            </div>
            {accounts.length === 0 ? (
              <div className="nc-empty">
                {(data.accounts || []).length === 0
                  ? 'Нет аккаунтов в пуле'
                  : settings.hide_in_work || settings.require_proxy
                    ? 'Нет аккаунтов, соответствующих фильтрам. Снимите «Рабочие прокси» или «Скрыть в работе».'
                    : 'Нет аккаунтов, соответствующих фильтрам'}
              </div>
            ) : (
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
              <strong>Выбрано для нейроблога {chosenAccounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: [] })}>Удалить все</button>
            </div>
            {chosenAccounts.length === 0 ? <div className="nc-empty">Аккаунты не выбраны</div> : (
              <div className="nc-list">
                {chosenAccounts.map((item) => (
                  <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>
                        {item.daily_messages_sent || 0} действий сегодня
                        {item.channel_attached ? ' · канал прикреплён' : item.channel_status === 'created' ? ' · канал создан' : ''}
                      </span>
                    </div>
                    <span>×</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head"><h2>Канал</h2></div>
          <label>
            Название
            <input className="nc-input" value={settings.channel_title || ''} onChange={(event) => patch({ channel_title: event.target.value })} />
          </label>
          <label>
            Описание канала
            <textarea className="nc-area" rows={3} value={settings.channel_about || ''} onChange={(event) => patch({ channel_about: event.target.value })} />
          </label>
          <p className="nc-hint">Это about самого канала. Профиль аккаунта не трогаем: канал виден как личный Telegram-канал.</p>
          <div className="nc-field">
            <span className="nc-field-label">Аватарка канала</span>
            <CustomFileButton
              variant="ubt"
              accept="image/png,image/jpeg,image/webp"
              busy={busy}
              fileName={avatarFileName || (settings.avatar_uploaded ? 'Сохранена на сервере' : '')}
              onFile={(file) => {
                setAvatarFileName(file.name);
                runSafe(async () => {
                  if (dirtyRef.current) {
                    await persist();
                  }
                  applyPayload(await customService.uploadNeuroblogAvatar(id, file));
                }, 'Аватарка сохранена');
              }}
            >
              Выбрать фото
            </CustomFileButton>
            <p className="nc-hint">PNG, JPG или WebP, до 5 МБ. Применится ко всем каналам задачи при следующем проходе.</p>
          </div>
        </div>
        <div className="nc-card">
          <div className="nc-card-head"><h2>Расписание и темы</h2></div>
          <div className="nc-row">
            <span className="nc-muted">Постов в день</span>
            <Stepper value={settings.posts_per_day} min={1} max={5} onChange={(value) => patch({ posts_per_day: value })} />
          </div>
          <p className="nc-hint">Слоты случайные внутри рабочего окна фермы по Москве. Ночью молчим.</p>
          <div className="nc-row" style={{ marginTop: 8 }}>
            {themes.map((theme) => (
              <button
                key={theme.id}
                type="button"
                className={`nc-chip ${(settings.themes || []).includes(theme.id) ? 'is-on' : ''}`}
                onClick={() => toggleTheme(theme.id)}
              >
                {theme.label}
              </button>
            ))}
          </div>
          <p className="nc-hint">Картинка только для кейса и инфографики. Эксперт, блог и размышление уходят текстом.</p>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Свои модели</h2></div>
        <p className="nc-hint">Подключите ChatGPT, Claude, Grok или DeepSeek своим API-ключом. Ключ хранится шифром и на экран больше не возвращается.</p>
        <div className="nc-row">
          {textProviders.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nc-chip ${settings.text_provider === item.id ? 'is-on' : ''}`}
              onClick={() => setTextProvider(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="nc-grid" style={{ marginTop: 12 }}>
          <label>
            Модель текста
            <CustomSelect
              className="nc-select"
              value={settings.text_model || ''}
              options={modelOptions(activeText?.models)}
              onChange={(event) => patch({ text_model: event.target.value })}
            />
          </label>
          <label>
            API-ключ {settings.text_api_key_set ? `(сохранён ${settings.text_api_key_hint || ''})` : settings.text_key_source === 'server' ? '(серверный)' : ''}
            <input
              className="nc-input"
              type="password"
              autoComplete="new-password"
              value={textKey}
              placeholder={settings.text_api_key_set ? 'оставь пустым, чтобы не менять' : 'sk-...'}
              onChange={(event) => { setTextKey(event.target.value); setDirty(true); }}
            />
          </label>
        </div>
        <div className="nc-row" style={{ marginTop: 16 }}>
          <span className="nc-muted">Картинки</span>
          <button type="button" className={`nc-chip ${!settings.image_provider ? 'is-on' : ''}`} onClick={() => setImageProvider('')}>Без картинок</button>
          {imageProviders.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nc-chip ${settings.image_provider === item.id ? 'is-on' : ''}`}
              onClick={() => setImageProvider(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <p className="nc-hint">Claude и DeepSeek картинки не рисуют. Для кейса и инфографики нужен ChatGPT или Grok.</p>
        {settings.image_provider ? (
          <div className="nc-grid" style={{ marginTop: 12 }}>
            <label>
              Модель картинок
              <CustomSelect
                className="nc-select"
                value={settings.image_model || ''}
                options={modelOptions(activeImage?.models)}
                onChange={(event) => patch({ image_model: event.target.value })}
              />
            </label>
            <label>
              API-ключ картинок {settings.image_api_key_set ? `(сохранён ${settings.image_api_key_hint || ''})` : settings.text_provider === settings.image_provider ? '(можно тот же, что у текста)' : ''}
              <input
                className="nc-input"
                type="password"
                autoComplete="new-password"
                value={imageKey}
                placeholder={settings.image_api_key_set ? 'оставь пустым, чтобы не менять' : 'ключ или пусто — взять текстовый'}
                onChange={(event) => { setImageKey(event.target.value); setDirty(true); }}
              />
            </label>
          </div>
        ) : null}
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Стилистика и продукт</h2></div>
        <label>
          Стилистика
          <textarea className="nc-area" rows={2} value={settings.style || ''} onChange={(event) => patch({ style: event.target.value })} />
        </label>
        <div className="nc-grid">
          <label>
            Продукт
            <input className="nc-input" value={settings.product_name || ''} onChange={(event) => patch({ product_name: event.target.value })} placeholder="Как называть продукт в постах" />
          </label>
          <label>
            Ссылка на продукт
            <input className="nc-input" value={settings.product_url || ''} onChange={(event) => patch({ product_url: event.target.value })} placeholder="Только внутри поста, если уместно" />
          </label>
        </div>
        <label>
          Промпт
          <textarea className="nc-area" rows={5} value={settings.prompt || ''} onChange={(event) => patch({ prompt: event.target.value })} placeholder="Что важно держать в голове автору: тон, табу, факты" />
        </label>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        <div className="nc-kpis nc-kpis--5">
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{data.summary?.attached || 0}</strong><span>Личных каналов</span></div>
          <div className="nc-kpi"><strong>{settings.posts_per_day}</strong><span>Постов / день</span></div>
          <div className="nc-kpi"><strong>{data.summary?.posts_today || 0}</strong><span>Уже сегодня</span></div>
          <div className="nc-kpi"><strong>{(data.next_slots || []).length}</strong><span>Слотов</span></div>
        </div>
        {(data.next_slots || []).length ? (
          <p className="nc-hint" style={{ marginTop: 10 }}>
            Ближайшие слоты: {(data.next_slots || []).map((item) => formatWhen(item)).join(' · ')}
          </p>
        ) : null}
        {issues.length ? (
          <div className="nc-alert" style={{ marginTop: 12 }}>
            <strong>Чтобы запустить</strong>
            {issues.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        {notices.length ? (
          <div className="nc-note" style={{ marginTop: 12 }}>
            {notices.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        <div className="nc-logs" style={{ marginTop: 12 }}>
          {(data.logs || []).length === 0 ? 'Логи появятся после запуска.' : (data.logs || []).map((row, index) => (
            <div key={`${row.at}-${index}`}>{formatWhen(row.at)} {row.message}</div>
          ))}
        </div>
        <UbtUnsaved dirty={dirty} />
        <div className="nc-launch" style={{ marginTop: 12 }}>
          <div className="nc-status">
            <span className={`nc-dot ${enabled ? 'is-on' : ''}`} />
            {enabled ? 'Модуль пишет по слотам' : 'Остановлено'}
          </div>
          <div className="nc-row">
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => persist(), 'Сохранено')}>Сохранить</button>
            <button
              type="button"
              className="acc-btn acc-btn--primary"
              disabled={busy || !enabled || (issues.length > 0 && !dirty)}
              onClick={() => runSafe(async () => {
                const saved = assertCanRun(await persist());
                applyPayload(await customService.runNeuroblogModule(id));
                return saved;
              }, 'Пост поставлен в каналы')}
            >
              Сгенерировать сейчас
            </button>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'tasks')}>Все задачи</Link>
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Последние посты</h2></div>
        {(data.posts || []).length === 0 ? (
          <p className="nc-muted">Постов ещё нет. Включите модуль или нажмите «Сгенерировать сейчас».</p>
        ) : (data.posts || []).map((post) => (
          <article key={`${post.at}-${post.theme}`} className="nc-post">
            <b>{themeLabel(post.theme)}</b>
            <p>{post.text}</p>
            <small>ушло в {(post.sent || []).length} каналов{post.image_path ? ' · с картинкой' : ''}</small>
          </article>
        ))}
      </div>
    </div>
  );
};

export default CustomAutomationNeuroblogPage;
