import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import customService, { mediaUrl } from '../../../services/customService';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import CustomBulkProfileForm from './CustomBulkProfileForm';
import CustomAccountConnectForm from './CustomAccountConnectForm';
import CustomAccountProxyFields from './CustomAccountProxyFields';
import { WARMUP_STATUS_LABELS } from './activityLabels';
import { ubtModulePath } from './customNav';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';

const PAGE_SIZES = [25, 50, 100];
const ACCEPT = '.zip,.csv,.session';

const STATUS_FILTERS = [
  { value: '', label: 'Все статусы' },
  { value: 'active', label: 'Активен' },
  { value: 'in_work', label: 'В работе' },
  { value: 'quarantine', label: 'На карантине' },
  { value: 'spamblock', label: 'Спамблок' },
  { value: 'invalid', label: 'Невалидные' },
  { value: 'frozen', label: 'Заморожен' },
  { value: 'banned', label: 'Реактивация' },
  { value: 'channel_banned', label: 'Бан в каналах' },
  { value: 'revoked', label: 'Сессия отозвана' },
  { value: 'empty', label: 'Пусто' },
];

const Ico = ({ d, children }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {d ? <path d={d} /> : children}
  </svg>
);

const KPI_CARDS = [
  { key: 'active', stat: 'active', label: 'Активные', tone: 'blue', icon: <Ico><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></Ico> },
  { key: 'in_work', stat: 'in_work', label: 'В работе', tone: 'cyan', icon: <Ico><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Ico> },
  { key: 'quarantine', stat: 'quarantine', label: 'На карантине', tone: 'violet', icon: <Ico d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /> },
  { key: 'spamblock', stat: 'spamblocked', label: 'Спамблок', tone: 'rose', icon: <Ico><circle cx="12" cy="12" r="9" /><path d="M5 5l14 14" /></Ico> },
  { key: 'invalid', stat: 'invalid', label: 'Невалидные', tone: 'amber', icon: <Ico><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /><path d="M18 8l4 4M22 8l-4 4" /></Ico> },
  { key: 'frozen', stat: 'frozen', label: 'Замороженные', tone: 'sky', icon: <Ico><path d="M12 2v20M4.9 7.5l14.2 9M4.9 16.5l14.2-9" /></Ico> },
  { key: 'banned', stat: 'banned', label: 'Реактивация', tone: 'orange', icon: <Ico d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /> },
  { key: 'channel_banned', stat: 'channel_banned', label: 'Бан в каналах', tone: 'slate', icon: <Ico d="M5 15H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h1m14 9h1a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-1M8 20h8M9 8v8a3 3 0 0 0 6 0V8" /> },
];

const formatRelative = (value) => {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) {
    return 'только что';
  }
  if (minutes < 60) {
    return `${minutes} мин назад`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours} ч назад`;
  }
  const days = Math.round(hours / 24);
  if (days < 14) {
    return `${days} дн назад`;
  }
  return date.toLocaleDateString('ru-RU');
};

const accountTitle = (account) =>
  account.display_name || (account.username ? `@${account.username}` : null) || account.phone_number || `ID ${account.id}`;

const initialsOf = (account) => {
  const name = accountTitle(account).replace('@', '');
  const parts = String(name).split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || '?';
};

const statusMeta = (account) => {
  if (account.is_banned) {
    return { label: 'Бан', chip: 'bad' };
  }
  if (account.is_frozen) {
    return { label: 'Заморожен', chip: 'info' };
  }
  if (account.status === 'revoked' || account.is_active === false) {
    return { label: 'Отозван', chip: 'warn' };
  }
  if (account.status === 'empty' || !account.session_file_path) {
    return { label: 'Пусто', chip: 'mute' };
  }
  return { label: 'Активен', chip: 'ok' };
};

const constraintMeta = (account) => {
  if (account.is_channel_banned) {
    return { label: 'Бан в каналах', chip: 'bad' };
  }
  if (account.is_frozen) {
    return { label: 'Frozen', chip: 'info' };
  }
  if (account.warmup_status === 'rest' || account.warmup_status === 'warming') {
    return { label: WARMUP_STATUS_LABELS[account.warmup_status] || 'Карантин', chip: 'warn' };
  }
  return { label: '—', chip: 'mute' };
};

const CustomAutomationAccountsPage = () => {
  const { id } = useParams();
  const { isAdmin } = useCustomAuth();
  const importInputRef = useRef(null);
  const dragCount = useRef(0);

  const [accounts, setAccounts] = useState([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSummary, setUploadSummary] = useState(null);
  const [prepareStatus, setPrepareStatus] = useState(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [banStats, setBanStats] = useState(null);
  const [healthCheckMessage, setHealthCheckMessage] = useState(null);
  const [isHealthChecking, setIsHealthChecking] = useState(false);
  const [checkingSpamblockId, setCheckingSpamblockId] = useState(null);
  const [spamblockMessage, setSpamblockMessage] = useState(null);
  const [warmupEnabled, setWarmupEnabled] = useState(false);
  const [isStartingWarmup, setIsStartingWarmup] = useState(false);
  const [warmupMessage, setWarmupMessage] = useState(null);
  const [savingNameId, setSavingNameId] = useState(null);
  const [nameDrafts, setNameDrafts] = useState({});
  const [bioDrafts, setBioDrafts] = useState({});
  const [filters, setFilters] = useState({ status: '', search: '', limit: 25, offset: 0 });
  const [searchInput, setSearchInput] = useState('');
  const [poolProxies, setPoolProxies] = useState([]);
  const [uploadProxyId, setUploadProxyId] = useState('');
  const [uploadProxyLine, setUploadProxyLine] = useState('');
  const [loginCodes, setLoginCodes] = useState({});
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [panel, setPanel] = useState(null);
  const [drawerId, setDrawerId] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [proxyText, setProxyText] = useState('');
  const [proxySaving, setProxySaving] = useState(false);
  const [proxyMessage, setProxyMessage] = useState(null);

  const loadAccounts = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationAccounts(id, {
        status: filters.status || undefined,
        search: filters.search || undefined,
        limit: filters.limit,
        offset: filters.offset,
      });
      setAccounts(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить аккаунты');
    } finally {
      setIsLoading(false);
    }
  }, [id, filters.status, filters.search, filters.limit, filters.offset]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const loadBanStats = useCallback(async () => {
    try {
      const data = await customService.getAutomationAccountBanStats(id);
      setBanStats(data);
    } catch {
      setBanStats(null);
    }
  }, [id]);

  useEffect(() => {
    loadBanStats();
  }, [loadBanStats]);

  const loadPoolProxies = useCallback(async () => {
    try {
      const data = await customService.listAccountProxies(id);
      setPoolProxies(data.items || []);
    } catch {
      setPoolProxies([]);
    }
  }, [id]);

  useEffect(() => {
    loadPoolProxies();
  }, [loadPoolProxies]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setFilters((prev) => (prev.search === searchInput ? prev : { ...prev, search: searchInput, offset: 0 }));
    }, 280);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    customService
      .getAutomationSettings(id)
      .then((data) => {
        setWarmupEnabled(Boolean(data.account_warmup_enabled));
        setProxyText(data.proxy_list_text || '');
      })
      .catch(() => {});
  }, [id]);

  useEffect(() => {
    if (!uploadSummary || !id) {
      return undefined;
    }
    let stopped = false;
    const tick = async () => {
      try {
        await loadBanStats();
      } catch {
        // ignore
      }
      if (!stopped) {
        timer = window.setTimeout(tick, 4000);
      }
    };
    let timer = window.setTimeout(tick, 2500);
    const stop = window.setTimeout(() => {
      stopped = true;
      window.clearTimeout(timer);
    }, 90000);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      window.clearTimeout(stop);
    };
  }, [uploadSummary, id, loadBanStats]);

  const handlePrepare = async () => {
    setIsPreparing(true);
    setError(null);
    try {
      const started = await customService.startAccountPrepare(id);
      setPrepareStatus(started);
    } catch (err) {
      setError(err.message || 'Не удалось начать подготовку');
      setIsPreparing(false);
    }
  };

  useEffect(() => {
    if (!prepareStatus || prepareStatus.status === 'completed' || prepareStatus.status === 'error' || !id) {
      if (prepareStatus && prepareStatus.status !== 'running') {
        setIsPreparing(false);
      }
      return undefined;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await customService.getAccountPrepareStatus(id);
        if (!cancelled) {
          setPrepareStatus(data);
          if (data.status === 'completed') {
            await loadAccounts();
            await loadBanStats();
          }
        }
      } catch {
        // ignore
      }
    };
    const timer = window.setInterval(poll, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [prepareStatus, id, loadAccounts, loadBanStats]);

  const handleHealthCheck = async () => {
    setHealthCheckMessage(null);
    setIsHealthChecking(true);
    try {
      const result = await customService.runAutomationAccountHealthCheck(id);
      setHealthCheckMessage(
        `Проверено: ${result.total}, OK: ${result.ok}, fallback: ${result.fallback}, ошибок: ${result.error}`,
      );
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setHealthCheckMessage(err.message || 'Не удалось проверить аккаунты');
    } finally {
      setIsHealthChecking(false);
    }
  };

  const handleCheckSpamblock = async (account) => {
    setCheckingSpamblockId(account.id);
    setSpamblockMessage(null);
    setError(null);
    try {
      const result = await customService.checkAccountSpamblock(id, account.id);
      setSpamblockMessage(result.detail || (result.spamblocked ? 'СПАМБЛОК' : 'Ограничений нет'));
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setError(err.message || 'Не удалось проверить спамблок');
    } finally {
      setCheckingSpamblockId(null);
    }
  };

  const handleFileChange = async (file) => {
    if (!file) {
      return;
    }
    setUploadError(null);
    setUploadSuccess(null);
    setIsUploading(true);
    try {
      const result = await customService.bulkUploadAccounts(id, file, {
        proxyId: uploadProxyId,
        proxyLine: uploadProxyLine,
      });
      setUploadSummary({
        created: result.created,
        skipped: result.skipped,
        errors: (result.errors || []).length,
      });
      setPrepareStatus(null);
      setUploadSuccess(
        `Загружено: ${result.created}, пропущено: ${result.skipped}, ошибок: ${(result.errors || []).length}`,
      );
      setPanel(null);
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setUploadError(err.message || 'Не удалось загрузить файл');
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartWarmup = async () => {
    setWarmupMessage(null);
    setError(null);
    try {
      const data = await customService.startAccountWarmup(id);
      setWarmupEnabled(Boolean(data.account_warmup_enabled));
      setWarmupMessage('Прогрев включён. Он применится к аккаунтам, которые зальёте после этой кнопки.');
    } catch (err) {
      setError(err.message || 'Не удалось включить прогрев');
    } finally {
      setIsStartingWarmup(false);
    }
  };

  const handleSaveProfile = async (account) => {
    const name = (nameDrafts[account.id] ?? account.display_name ?? '').trim();
    const bio = (bioDrafts[account.id] ?? account.bio ?? '').trim();
    if (!name) {
      setError('Имя не может быть пустым');
      return;
    }
    setSavingNameId(account.id);
    setError(null);
    try {
      await customService.updateAccount(id, account.id, { displayName: name, bio });
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось сохранить профиль');
    } finally {
      setSavingNameId(null);
    }
  };

  const handleAccountAvatar = async (account, file) => {
    if (!file) {
      return;
    }
    setError(null);
    setUploadSuccess(null);
    try {
      const result = await customService.bulkUpdateProfiles(id, {
        avatar: file,
        accountIds: [account.id],
      });
      const failed = (result.results || []).find((row) => row.status === 'error');
      if (failed) {
        const raw = String(failed.error || '');
        const sessionLost = /нет входа|not authorized|sessioninvalid|session file missing/i.test(raw);
        setError(
          sessionLost
            ? 'Нет входа в Telegram. Подключите аккаунт заново по QR или SMS.'
            : (raw || 'Не удалось обновить аватар'),
        );
        return;
      }
      setUploadSuccess('Аватар обновлён');
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось обновить аватар');
    }
  };

  const handleDeleteAccount = async (account) => {
    const label = account.phone_number || account.username || `#${account.id}`;
    if (!window.confirm(`Удалить аккаунт ${label}?`)) {
      return;
    }
    try {
      await customService.deleteAccount(id, account.id);
      setDrawerId(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(account.id);
        return next;
      });
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setError(err.message || 'Не удалось удалить аккаунт');
    }
  };

  const handleBulkDelete = async () => {
    if (!selectedIds.size) {
      return;
    }
    if (!window.confirm(`Удалить выбранные аккаунты (${selectedIds.size})?`)) {
      return;
    }
    try {
      await Promise.all([...selectedIds].map((accountId) => customService.deleteAccount(id, accountId)));
      setSelectedIds(new Set());
      setDrawerId(null);
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setError(err.message || 'Не удалось удалить аккаунты');
    }
  };

  const handleTelegramCode = async (account) => {
    setLoginCodes((prev) => ({ ...prev, [account.id]: { loading: true } }));
    try {
      const data = await customService.getAccountTelegramCode(id, account.id);
      setLoginCodes((prev) => ({
        ...prev,
        [account.id]: {
          loading: false,
          code: data.code || null,
          sentAt: data.sent_at || null,
          detail: data.detail || '',
        },
      }));
    } catch (err) {
      setLoginCodes((prev) => ({
        ...prev,
        [account.id]: { loading: false, error: err.message || 'Не удалось прочитать код' },
      }));
    }
  };

  const handleSaveProxies = async () => {
    setProxySaving(true);
    setProxyMessage(null);
    try {
      await customService.updateAutomationSettings(id, { proxy_list_text: proxyText });
      await loadPoolProxies();
      setProxyMessage('Пул прокси сохранён');
    } catch (err) {
      setProxyMessage(err.message || 'Не удалось сохранить прокси');
    } finally {
      setProxySaving(false);
    }
  };

  const sortedAccounts = useMemo(() => {
    const rows = [...accounts];
    const dir = sortDir === 'asc' ? 1 : -1;
    const valueOf = (account) => {
      if (sortKey === 'name') {
        return accountTitle(account).toLowerCase();
      }
      if (sortKey === 'status') {
        return statusMeta(account).label;
      }
      if (sortKey === 'spamblock') {
        return account.is_spamblocked ? 1 : 0;
      }
      if (sortKey === 'constraint') {
        return constraintMeta(account).label;
      }
      if (sortKey === 'tracking') {
        return account.last_used_at || '';
      }
      if (sortKey === 'proxy') {
        return account.proxy_label || '';
      }
      return '';
    };
    rows.sort((a, b) => {
      const left = valueOf(a);
      const right = valueOf(b);
      if (left < right) {
        return -1 * dir;
      }
      if (left > right) {
        return 1 * dir;
      }
      return 0;
    });
    return rows;
  }, [accounts, sortKey, sortDir]);

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDir('asc');
  };

  const toggleKpi = (status) => {
    setFilters((prev) => ({
      ...prev,
      status: prev.status === status ? '' : status,
      offset: 0,
    }));
    setSelectedIds(new Set());
  };

  const toggleRow = (accountId, checked) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(accountId);
      } else {
        next.delete(accountId);
      }
      return next;
    });
  };

  const allChecked = accounts.length > 0 && accounts.every((item) => selectedIds.has(item.id));
  const hasFilters = Boolean(filters.status || filters.search);
  const showEmpty = !isLoading && total === 0 && !hasFilters;
  const from = total === 0 ? 0 : filters.offset + 1;
  const to = Math.min(filters.offset + accounts.length, total);
  const pageCount = Math.max(1, Math.ceil(total / filters.limit) || 1);
  const page = Math.floor(filters.offset / filters.limit) + 1;
  const drawerAccount = accounts.find((item) => item.id === drawerId) || null;
  const warmupPath = ubtModulePath(id, 'warmup');

  const goPage = (nextPage) => {
    const clamped = Math.min(pageCount, Math.max(1, nextPage));
    setFilters((prev) => ({ ...prev, offset: (clamped - 1) * prev.limit }));
  };

  const onDragEnter = (event) => {
    event.preventDefault();
    dragCount.current += 1;
    setIsDragging(true);
  };

  const onDragOver = (event) => {
    event.preventDefault();
  };

  const onDragLeave = () => {
    dragCount.current -= 1;
    if (dragCount.current <= 0) {
      dragCount.current = 0;
      setIsDragging(false);
    }
  };

  const onDrop = (event) => {
    event.preventDefault();
    dragCount.current = 0;
    setIsDragging(false);
    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) {
      handleFileChange(file);
    }
  };

  const flashes = [
    warmupMessage,
    healthCheckMessage,
    spamblockMessage,
    uploadSuccess,
    prepareStatus?.status === 'running'
      ? `Подготовка: живых ${prepareStatus.alive || 0}, профили ${prepareStatus.profiles_done || 0}, чаты ${prepareStatus.chats_joined || 0}`
      : null,
    prepareStatus?.status === 'completed' ? 'Подготовка завершена' : null,
    prepareStatus?.status === 'error' ? prepareStatus.error : null,
  ].filter(Boolean);

  return (
    <div
      className="acc-manager"
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <input
        ref={importInputRef}
        type="file"
        accept={ACCEPT}
        className="acc-hidden-file"
        onChange={(event) => {
          const file = event.target.files && event.target.files[0];
          if (file) {
            handleFileChange(file);
          }
          event.target.value = '';
        }}
      />

      {flashes.map((text) => (
        <p key={text} className="acc-flash">{text}</p>
      ))}
      {uploadError ? <p className="acc-flash acc-flash--error">{uploadError}</p> : null}
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {banStats?.alert ? (
        <p className="acc-flash acc-flash--alert">
          Высокий процент банов: {banStats.banned} из {banStats.total} ({(banStats.banned_percent * 100).toFixed(0)}%).
        </p>
      ) : null}
      {uploadSummary && !prepareStatus ? (
        <p className="acc-flash">
          Залито {uploadSummary.created} сессий.
          {' '}
          <button type="button" className="acc-btn acc-btn--primary" onClick={handlePrepare} disabled={isPreparing}>
            {isPreparing ? 'Подготовка...' : 'Подготовить профили и вступить в чаты'}
          </button>
        </p>
      ) : null}

      <div className="acc-kpis">
        {KPI_CARDS.map((card) => (
          <button
            key={card.key}
            type="button"
            className={`acc-kpi ${filters.status === card.key ? 'is-active' : ''}`}
            onClick={() => toggleKpi(card.key)}
          >
            <span className={`acc-kpi-icon acc-kpi-icon--${card.tone}`}>
              {card.icon}
            </span>
            <strong>{banStats ? banStats[card.stat] || 0 : '…'}</strong>
            <span>{card.label}</span>
          </button>
        ))}
      </div>

      <div className="acc-cta">
        <button type="button" className="acc-btn acc-btn--primary" onClick={() => { setDrawerId(null); setPanel('import'); }} disabled={isUploading}>
          <Ico d="M12 3v12M8 11l4 4 4-4M4 21h16" />
          Импортировать аккаунты
        </button>
        <button type="button" className="acc-btn acc-btn--ghost" onClick={() => { setDrawerId(null); setPanel('add'); }}>
          <Ico><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M16 11h6" /></Ico>
          Добавить аккаунт
        </button>
        <button type="button" className="acc-btn acc-btn--mint" onClick={() => { setDrawerId(null); setPanel('proxy'); }}>
          <Ico><rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a4 4 0 0 0-8 0v2" /></Ico>
          Пул прокси
        </button>
      </div>

      <div className="acc-table-card">
        <div className="acc-toolbar">
          <form className="acc-search" onSubmit={(event) => event.preventDefault()}>
            <Ico><circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" /></Ico>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Поиск по имени, номеру, username..."
            />
          </form>
          <div className="acc-tools">
            <button
              type="button"
              className={`acc-icon-btn ${filterOpen ? 'is-active' : ''}`}
              title="Фильтры"
              onClick={() => setFilterOpen((open) => !open)}
            >
              <Ico d="M4 4h16l-6 8v6l-4 2v-8L4 4z" />
            </button>
            <button type="button" className="acc-icon-btn" title="Профили" onClick={() => { setDrawerId(null); setPanel('profiles'); }}>
              <Ico><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 8h10M7 12h6" /></Ico>
            </button>
            <button type="button" className="acc-icon-btn" title="Проверить сессии" onClick={handleHealthCheck} disabled={isHealthChecking}>
              <Ico><path d="M21 12a9 9 0 1 1-3-6.7" /><path d="M21 3v6h-6" /></Ico>
            </button>
            <Link className="acc-icon-btn" title="Прогрев аккаунтов" to={warmupPath}>
              <Ico d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
            </Link>
            <button
              type="button"
              className="acc-icon-btn"
              title="Удалить выбранные"
              onClick={handleBulkDelete}
              disabled={!selectedIds.size}
            >
              <Ico d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
            </button>
            {filterOpen ? (
              <div className="acc-filter-pop">
                <div>
                  <label htmlFor="acc-filter-status">Статус</label>
                  <CustomSelect
                    id="acc-filter-status"
                    value={filters.status}
                    options={STATUS_FILTERS}
                    onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value, offset: 0 }))}
                  />
                </div>
                <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'warmup')}>Прогрев</Link>
                {isAdmin && !warmupEnabled ? (
                  <button type="button" className="acc-btn acc-btn--ghost" onClick={handleStartWarmup} disabled={isStartingWarmup}>
                    {isStartingWarmup ? 'Включаем...' : 'Включить для новых заливов'}
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        {showEmpty ? (
          <div className="acc-empty">
            <div className="acc-drop">
              <span className="acc-drop-spark acc-drop-spark--tl">
                <Ico d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
              </span>
              <span className="acc-drop-mark">
                <Ico d="M12 16V6M8 10l4-4 4 4M4 20h16" />
              </span>
              <span className="acc-drop-spark acc-drop-spark--tr">
                <Ico><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /></Ico>
              </span>
            </div>
            <p className="acc-empty-kicker">Telegram-комбайн</p>
            <h2>Здесь появятся ваши аккаунты</h2>
            <p>
              Перетащите файлы прямо сюда или импортируйте вручную — комбайн подхватит сессии сам.
            </p>
            <div className="acc-empty-actions">
              <button type="button" className="acc-btn acc-btn--primary" onClick={() => importInputRef.current?.click()} disabled={isUploading}>
                Импортировать аккаунты
              </button>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => { setDrawerId(null); setPanel('add'); }}>
                Добавить вручную
              </button>
            </div>
            <div className="acc-formats">
              <b>Форматы</b>
              <span className="acc-format">.session</span>
              <span className="acc-format">.zip</span>
              <span className="acc-format">.csv</span>
            </div>
          </div>
        ) : (
          <div className="acc-table-wrap">
            <table className="acc-table">
              <thead>
                <tr>
                  <th className="acc-check">
                    <input
                      type="checkbox"
                      checked={allChecked}
                      onChange={(event) => {
                        if (event.target.checked) {
                          setSelectedIds(new Set(accounts.map((item) => item.id)));
                        } else {
                          setSelectedIds(new Set());
                        }
                      }}
                    />
                  </th>
                  <th>Аватар</th>
                  <th><button type="button" onClick={() => toggleSort('name')}>Имя</button></th>
                  <th><button type="button" onClick={() => toggleSort('status')}>Статус</button></th>
                  <th><button type="button" onClick={() => toggleSort('spamblock')}>Спамблок</button></th>
                  <th><button type="button" onClick={() => toggleSort('constraint')}>Статус C</button></th>
                  <th><button type="button" onClick={() => toggleSort('tracking')}>Отлёжка</button></th>
                  <th><button type="button" onClick={() => toggleSort('proxy')}>Прокси</button></th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={9}>Загрузка...</td>
                  </tr>
                ) : sortedAccounts.length === 0 ? (
                  <tr>
                    <td colSpan={9}>Ничего не найдено по текущим фильтрам.</td>
                  </tr>
                ) : (
                  sortedAccounts.map((account) => {
                    const status = statusMeta(account);
                    const constraint = constraintMeta(account);
                    const avatarSrc = mediaUrl(account.avatar_url, account.updated_at || account.last_health_check_at);
                    return (
                      <tr
                        key={account.id}
                        className={drawerId === account.id ? 'is-open' : ''}
                        onClick={() => { setPanel(null); setDrawerId(account.id); }}
                      >
                        <td className="acc-check" onClick={(event) => event.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(account.id)}
                            onChange={(event) => toggleRow(account.id, event.target.checked)}
                          />
                        </td>
                        <td>
                          {avatarSrc ? (
                            <img className="acc-avatar" src={avatarSrc} alt="" />
                          ) : (
                            <span className="acc-avatar">{initialsOf(account)}</span>
                          )}
                        </td>
                        <td>
                          <div className="acc-user">
                            <b>{accountTitle(account)}</b>
                            <small>
                              {account.username ? `@${account.username}` : account.phone_number || `#${account.id}`}
                            </small>
                          </div>
                        </td>
                        <td><span className={`acc-chip acc-chip--${status.chip}`}>{status.label}</span></td>
                        <td>
                          <span className={`acc-chip acc-chip--${account.is_spamblocked ? 'bad' : 'ok'}`}>
                            {account.is_spamblocked ? 'Да' : 'Нет'}
                          </span>
                        </td>
                        <td><span className={`acc-chip acc-chip--${constraint.chip}`}>{constraint.label}</span></td>
                        <td>{formatRelative(account.last_used_at)}</td>
                        <td>{account.proxy_label || 'Авто'}</td>
                        <td onClick={(event) => event.stopPropagation()}>
                          <button type="button" className="acc-icon-btn" onClick={() => { setPanel(null); setDrawerId(account.id); }} title="Карточка">
                            <Ico><circle cx="12" cy="5" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="12" cy="19" r="1" /></Ico>
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="acc-pager">
          <div className="acc-pager-btns">
            <button type="button" className="acc-icon-btn" onClick={() => goPage(1)} disabled={page <= 1}>«</button>
            <button type="button" className="acc-icon-btn" onClick={() => goPage(page - 1)} disabled={page <= 1}>‹</button>
            <button type="button" className="acc-icon-btn" onClick={() => goPage(page + 1)} disabled={page >= pageCount}>›</button>
            <button type="button" className="acc-icon-btn" onClick={() => goPage(pageCount)} disabled={page >= pageCount}>»</button>
          </div>
          <span>Показано {from}–{to} из {total} аккаунтов</span>
          <CustomSelect
            value={String(filters.limit)}
            options={PAGE_SIZES.map((size) => ({ value: String(size), label: String(size) }))}
            onChange={(event) => setFilters((prev) => ({ ...prev, limit: Number(event.target.value), offset: 0 }))}
          />
        </div>
      </div>

      {isDragging ? <div className="acc-drop-overlay">Отпустите файл для импорта</div> : null}

      {panel ? (
        <div className="acc-drawer-backdrop" onClick={() => setPanel(null)}>
          <aside className="acc-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="acc-drawer-head">
              <div>
                <h2>
                  {panel === 'import' && 'Импорт аккаунтов'}
                  {panel === 'add' && 'Добавить аккаунт'}
                  {panel === 'proxy' && 'Пул прокси'}
                  {panel === 'profiles' && 'Массовое обновление профилей'}
                </h2>
                <p>
                  {panel === 'import' && 'ZIP с .session, одиночный .session или CSV.'}
                  {panel === 'add' && 'QR или код из SMS. 2FA — если включена.'}
                  {panel === 'proxy' && 'Список для автоназначения при заливе и подключении.'}
                  {panel === 'profiles' && 'Имя, bio и аватар сразу на пачку аккаунтов.'}
                </p>
              </div>
              <button type="button" className="acc-icon-btn" onClick={() => setPanel(null)}>×</button>
            </div>
            <div className="acc-drawer-body">
              {panel === 'import' ? (
                <>
                  <CustomAccountProxyFields
                    proxies={poolProxies}
                    proxyId={uploadProxyId}
                    proxyLine={uploadProxyLine}
                    onProxyIdChange={setUploadProxyId}
                    onProxyLineChange={setUploadProxyLine}
                    disabled={isUploading}
                  />
                  <button
                    type="button"
                    className="acc-btn acc-btn--primary"
                    onClick={() => importInputRef.current?.click()}
                    disabled={isUploading}
                  >
                    {isUploading ? 'Загрузка...' : 'Выбрать файл'}
                  </button>
                </>
              ) : null}
              {panel === 'add' ? (
                <CustomAccountConnectForm
                  automationId={id}
                  hideTitle
                  onConnected={async () => {
                    await loadAccounts();
                    await loadBanStats();
                  }}
                />
              ) : null}
              {panel === 'proxy' ? (
                <>
                  <p className="form-hint">
                    В пуле сейчас: {poolProxies.length || 'пусто'}.
                  </p>
                  {proxyMessage ? <p className="form-hint">{proxyMessage}</p> : null}
                  <div className="form-group">
                    <label htmlFor="acc-proxy-text">Список прокси</label>
                    <textarea
                      id="acc-proxy-text"
                      rows={8}
                      value={proxyText}
                      onChange={(event) => setProxyText(event.target.value)}
                      placeholder={'1.2.3.4:1080\n5.6.7.8:1080:user:pass\nsocks5://user:pass@9.8.7.6:1080'}
                    />
                  </div>
                  <CustomFileButton
                    variant="ubt"
                    accept=".txt,text/plain"
                    onFile={async (file) => setProxyText(await file.text())}
                  >
                    Загрузить .txt
                  </CustomFileButton>
                  <button type="button" className="acc-btn acc-btn--dark" onClick={handleSaveProxies} disabled={proxySaving}>
                    {proxySaving ? 'Сохранение...' : 'Сохранить пул'}
                  </button>
                </>
              ) : null}
              {panel === 'profiles' ? (
                <CustomBulkProfileForm
                  automationId={id}
                  embedded
                  onSuccess={loadAccounts}
                />
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}

      {drawerAccount ? (
        <div className="acc-drawer-backdrop" onClick={() => setDrawerId(null)}>
          <aside className="acc-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="acc-drawer-head">
              <div>
                <h2>{accountTitle(drawerAccount)}</h2>
                <p>
                  {drawerAccount.username ? `@${drawerAccount.username}` : ''}
                  {drawerAccount.phone_number ? ` ${drawerAccount.phone_number}` : ''}
                </p>
              </div>
              <button type="button" className="acc-icon-btn" onClick={() => setDrawerId(null)}>×</button>
            </div>
            <div className="acc-drawer-body">
              <div>
                <span className={`acc-chip acc-chip--${statusMeta(drawerAccount).chip}`}>{statusMeta(drawerAccount).label}</span>
                {drawerAccount.is_spamblocked ? <span className="acc-chip acc-chip--bad">Спамблок</span> : null}
                {drawerAccount.is_channel_banned ? <span className="acc-chip acc-chip--bad">Бан в каналах</span> : null}
              </div>
              <div className="form-group">
                <label htmlFor="acc-name">Имя</label>
                <input
                  id="acc-name"
                  value={nameDrafts[drawerAccount.id] ?? drawerAccount.display_name ?? ''}
                  onChange={(event) => setNameDrafts((prev) => ({ ...prev, [drawerAccount.id]: event.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="acc-bio">Bio</label>
                <textarea
                  id="acc-bio"
                  rows={3}
                  value={bioDrafts[drawerAccount.id] ?? drawerAccount.bio ?? ''}
                  onChange={(event) => setBioDrafts((prev) => ({ ...prev, [drawerAccount.id]: event.target.value }))}
                />
              </div>
              <div className="acc-cta" style={{ justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="acc-btn acc-btn--dark"
                  onClick={() => handleSaveProfile(drawerAccount)}
                  disabled={savingNameId === drawerAccount.id}
                >
                  {savingNameId === drawerAccount.id ? 'Сохранение...' : 'Сохранить профиль'}
                </button>
                <CustomFileButton variant="ubt" accept="image/*" onFile={(file) => handleAccountAvatar(drawerAccount, file)}>
                  Аватар
                </CustomFileButton>
              </div>
              <p className="form-hint">
                Прокси: {drawerAccount.proxy_label || 'авто из пула'}. Отлёжка: {formatRelative(drawerAccount.last_used_at)}.
                {drawerAccount.warmup_status && drawerAccount.warmup_status !== 'idle'
                  ? ` ${WARMUP_STATUS_LABELS[drawerAccount.warmup_status] || drawerAccount.warmup_status}.`
                  : ''}
              </p>
              <div className="acc-cta" style={{ justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="acc-btn acc-btn--ghost"
                  onClick={() => handleCheckSpamblock(drawerAccount)}
                  disabled={checkingSpamblockId === drawerAccount.id}
                >
                  {checkingSpamblockId === drawerAccount.id ? 'Проверка...' : 'Проверить спамблок'}
                </button>
                <button type="button" className="acc-btn acc-btn--ghost" onClick={() => handleTelegramCode(drawerAccount)}>
                  {loginCodes[drawerAccount.id]?.loading ? 'Читаем...' : 'Код из Telegram'}
                </button>
                <button type="button" className="acc-btn acc-btn--ghost" onClick={() => handleDeleteAccount(drawerAccount)}>
                  Удалить
                </button>
              </div>
              {loginCodes[drawerAccount.id]?.code ? (
                <p className="acc-flash">Код: {loginCodes[drawerAccount.id].code}</p>
              ) : null}
              {loginCodes[drawerAccount.id]?.detail && !loginCodes[drawerAccount.id]?.code ? (
                <p className="form-hint">{loginCodes[drawerAccount.id].detail}</p>
              ) : null}
              {loginCodes[drawerAccount.id]?.error ? (
                <p className="acc-flash acc-flash--error">{loginCodes[drawerAccount.id].error}</p>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationAccountsPage;
