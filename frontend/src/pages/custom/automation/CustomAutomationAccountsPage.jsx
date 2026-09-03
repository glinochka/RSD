import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import customService, { mediaUrl } from '../../../services/customService';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import CustomBulkProfileForm from './CustomBulkProfileForm';
import CustomAccountConnectForm from './CustomAccountConnectForm';
import { ACCOUNT_ROLE_LABELS, ACCOUNT_ROLE_OPTIONS, WARMUP_STATUS_LABELS } from './activityLabels';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

const ACCOUNT_CLASSES = [
  { value: '', label: 'Все классы' },
  { value: 'one_day', label: 'Однодневный' },
  { value: 'mid', label: 'Средний' },
  { value: 'trusted', label: 'Доверенный' },
  { value: 'shilling', label: 'Шиллинг' },
];

const ROLE_FILTERS = [{ value: '', label: 'Все функции' }, ...ACCOUNT_ROLE_OPTIONS];

const CLASS_STATUS = {
  one_day: 'crm-status--pending',
  mid: 'crm-status--completed',
  trusted: 'crm-status--confirmed',
  shilling: 'crm-status--cancelled',
};

const STATUSES = [
  { value: '', label: 'Все статусы' },
  { value: 'active', label: 'Активен' },
  { value: 'revoked', label: 'Сессия отозвана' },
  { value: 'spamblock', label: 'СПАМБЛОК' },
  { value: 'banned', label: 'Бан' },
  { value: 'empty', label: 'Пусто' },
];

const CustomAutomationAccountsPage = () => {
  const { id } = useParams();
  const { isAdmin } = useCustomAuth();
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
  const [classifyMessage, setClassifyMessage] = useState(null);
  const [isClassifying, setIsClassifying] = useState(false);
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
  const [filters, setFilters] = useState({
    status: '',
    accountClass: '',
    role: '',
    search: '',
  });

  const loadAccounts = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationAccounts(id, {
        status: filters.status || undefined,
        accountClass: filters.accountClass || undefined,
        role: filters.role || undefined,
        search: filters.search || undefined,
        limit: 50,
        offset: 0,
      });
      setAccounts(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load accounts');
    } finally {
      setIsLoading(false);
    }
  }, [id, filters.status, filters.accountClass, filters.role, filters.search]);

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

  useEffect(() => {
    if (!isAdmin) {
      return undefined;
    }
    customService
      .getAutomationSettings(id)
      .then((data) => setWarmupEnabled(Boolean(data.account_warmup_enabled)))
      .catch(() => {});
    return undefined;
  }, [id, isAdmin]);

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
      setHealthCheckMessage(err.message || 'Health check failed');
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

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadAccounts();
  };

  const handleFileChange = async (file) => {
    if (!file) {
      return;
    }
    setUploadError(null);
    setUploadSuccess(null);
    setIsUploading(true);
    try {
      const result = await customService.bulkUploadAccounts(id, file, filters.accountClass || 'one_day');
      setUploadSummary({
        created: result.created,
        skipped: result.skipped,
        errors: (result.errors || []).length,
      });
      setPrepareStatus(null);
      setUploadSuccess(
        `Загружено: ${result.created}, пропущено: ${result.skipped}, ошибок: ${result.errors.length}`,
      );
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleBulkClassify = async () => {
    setClassifyMessage(null);
    setIsClassifying(true);
    try {
      const result = await customService.bulkClassifyAccounts(id, []);
      setClassifyMessage(`В очереди на проверку: ${result.queued}. Результат обновится после фоновой проверки.`);
    } catch (err) {
      setClassifyMessage(err.message || 'Classification failed');
    } finally {
      setIsClassifying(false);
    }
  };

  const handleClassChange = async (accountId, assignedClass) => {
    try {
      await customService.updateAccountClass(id, accountId, assignedClass);
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Failed to update class');
    }
  };

  const handleRolesChange = async (accountId, roles) => {
    try {
      await customService.updateAccount(id, accountId, { roles });
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось сохранить функции');
    }
  };

  const handleStartWarmup = async () => {
    setIsStartingWarmup(true);
    setWarmupMessage(null);
    setError(null);
    try {
      const data = await customService.startAccountWarmup(id);
      setWarmupEnabled(Boolean(data.account_warmup_enabled));
      setWarmupMessage('Прогрев включён. Он применится только к аккаунтам, которые зальёте после этой кнопки.');
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
      await loadAccounts();
      await loadBanStats();
    } catch (err) {
      setError(err.message || 'Не удалось удалить аккаунт');
    }
  };

  const accountStatusMeta = (account) => {
    if (account.is_banned) {
      return { label: 'Бан', className: 'crm-status--cancelled' };
    }
    if (account.status === 'revoked' || account.is_active === false) {
      return { label: 'Сессия отозвана', className: 'crm-status--revoked' };
    }
    if (account.status === 'empty') {
      return { label: 'Пусто', className: 'crm-status--pending' };
    }
    return { label: 'Активен', className: 'crm-status--confirmed' };
  };

  const roleDistribution = accounts.reduce((acc, a) => {
    (a.roles || []).forEach((role) => {
      acc[role] = (acc[role] || 0) + 1;
    });
    return acc;
  }, {});

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Аккаунты</h1>
          <p className="crm-subtitle">Один аккаунт по QR или SMS, либо массовый залив сессий.</p>
        </div>
        <div className="settings-actions">
          <button type="button" onClick={handleHealthCheck} disabled={isHealthChecking} className="btn btn-outline">
            {isHealthChecking ? 'Проверка...' : 'Проверить'}
          </button>
          <button type="button" onClick={handleBulkClassify} disabled={isClassifying} className="btn btn-outline">
            {isClassifying ? 'Проверка...' : 'Переклассифировать'}
          </button>
          <CustomFileButton
            accept=".zip,.csv,.session"
            variant="black"
            busy={isUploading}
            onFile={handleFileChange}
          >
            {isUploading ? 'Загрузка...' : 'Загрузить ZIP / CSV / .session'}
          </CustomFileButton>
        </div>
      </div>

      {warmupMessage ? <p className="crm-flash">{warmupMessage}</p> : null}
      {classifyMessage ? <p className="crm-flash">{classifyMessage}</p> : null}
      {healthCheckMessage ? <p className="crm-flash">{healthCheckMessage}</p> : null}
      {spamblockMessage ? <p className="crm-flash">{spamblockMessage}</p> : null}
      {uploadSuccess ? <p className="crm-flash">{uploadSuccess}</p> : null}
      {uploadError ? <p className="crm-flash crm-flash--error">{uploadError}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      {isAdmin ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Прогрев аккаунтов</h3>
          <p className="form-hint">
            После включения прогрев идёт только для следующих заливов: первый день — отдых, второй —
            мини-диалог с доверенным аккаунтом, на третий день то же и прогрев завершён.
            Юзернеймы задаются в настройках.
          </p>
          <p className="form-hint">
            {warmupEnabled ? 'Прогрев включён для новых заливов.' : 'Прогрев выключен.'}
          </p>
          <div className="settings-actions">
            <button
              type="button"
              className="btn btn-black"
              disabled={isStartingWarmup || warmupEnabled}
              onClick={handleStartWarmup}
            >
              {isStartingWarmup ? 'Включаем...' : warmupEnabled ? 'Прогрев включён' : 'Начать прогрев'}
            </button>
          </div>
        </div>
      ) : null}
      {uploadSummary ? (
        <div className="settings-section">
          <h3 className="settings-section-title">После залива</h3>
          <div className="crm-stats">
            <div className="crm-stat">
              <span className="crm-stat-value">{uploadSummary.created}</span>
              <span className="crm-stat-label">Залито сессий</span>
            </div>
            <div className="crm-stat">
              <span className="crm-stat-value">{banStats ? banStats.active : '…'}</span>
              <span className="crm-stat-label">Живые</span>
            </div>
          </div>
          {prepareStatus?.status === 'running' ? (
            <p className="form-hint">
              Подготовка: профили {prepareStatus.profiles_done || 0}, вступили в чаты {prepareStatus.chats_joined || 0}
            </p>
          ) : null}
          {prepareStatus?.status === 'completed' ? (
            <p className="form-hint">
              Готово: оформлено {prepareStatus.profiles_done || 0}, чатов {prepareStatus.chats_joined || 0}
            </p>
          ) : null}
          {prepareStatus?.status === 'error' ? (
            <p className="form-hint form-hint--error">{prepareStatus.error || 'Ошибка подготовки'}</p>
          ) : null}
          <p className="form-hint">
            Оформление идёт по шаблонам из «Массовое обновление профилей». Затем аккаунты вступают в уже загруженные чаты.
          </p>
          <div className="settings-actions">
            <button
              type="button"
              className="btn btn-black"
              disabled={isPreparing || prepareStatus?.status === 'running'}
              onClick={handlePrepare}
            >
              {isPreparing || prepareStatus?.status === 'running' ? 'Подготовка...' : 'Начать подготовку'}
            </button>
          </div>
        </div>
      ) : null}

      {banStats && banStats.alert ? (
        <div className="settings-section settings-section--danger">
          <h3 className="settings-section-title settings-section-title--danger">Высокий процент банов</h3>
          <p className="form-hint">
            Забанено {banStats.banned} из {banStats.total} ({(banStats.banned_percent * 100).toFixed(0)}%).
            Пополните пул или снизьте активность.
          </p>
        </div>
      ) : null}

      {banStats ? (
        <p className="form-hint">
          Активны {banStats.active}
          {banStats.revoked ? ` · отозваны ${banStats.revoked}` : ''}
          {banStats.spamblocked ? ` · СПАМБЛОК ${banStats.spamblocked}` : ''}
          {banStats.banned ? ` · бан ${banStats.banned}` : ''}
        </p>
      ) : null}

      {accounts.length > 0 ? (
        <div className="crm-stats">
          {ACCOUNT_ROLE_OPTIONS.map((c) => (
            <div key={c.value} className="crm-stat">
              <span className="crm-stat-value">{roleDistribution[c.value] || 0}</span>
              <span className="crm-stat-label">{c.label}</span>
            </div>
          ))}
          <div className="crm-stat">
            <span className="crm-stat-value">{total}</span>
            <span className="crm-stat-label">Всего</span>
          </div>
        </div>
      ) : null}

      <CustomAccountConnectForm automationId={id} onConnected={loadAccounts} />

      <CustomBulkProfileForm automationId={id} onSuccess={loadAccounts} />

      <form onSubmit={handleSearchSubmit} className="settings-section">
        <h3 className="settings-section-title">Фильтр</h3>
        <div className="form-group">
          <label htmlFor="acc-status">Статус</label>
          <CustomSelect
            id="acc-status"
            value={filters.status}
            options={STATUSES}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="acc-role">Функция</label>
          <CustomSelect
            id="acc-role"
            value={filters.role}
            options={ROLE_FILTERS}
            onChange={(e) => setFilters((f) => ({ ...f, role: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="acc-class">Класс</label>
          <CustomSelect
            id="acc-class"
            value={filters.accountClass}
            options={ACCOUNT_CLASSES}
            onChange={(e) => setFilters((f) => ({ ...f, accountClass: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="acc-search">Поиск</label>
          <input
            id="acc-search"
            type="text"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            placeholder="Телефон, username, имя"
          />
        </div>
        <div className="settings-actions">
          <button type="submit" className="btn btn-outline">Найти</button>
        </div>
      </form>

      {isLoading ? (
        <div className="crm-empty-list"><p>Загрузка...</p></div>
      ) : accounts.length === 0 ? (
        <div className="crm-empty-list">
          <p>Нет аккаунтов</p>
          <span>Добавьте по QR / SMS или загрузите ZIP с .session.</span>
        </div>
      ) : (
        <div className="crm-list">
          {accounts.map((account) => {
            const statusMeta = accountStatusMeta(account);
            const avatarSrc = mediaUrl(account.avatar_url, account.updated_at || account.last_health_check_at);
            const title = account.display_name || account.username || account.phone_number || `Аккаунт #${account.id}`;
            return (
            <div key={account.id} className="crm-item crm-account-card">
              <div className="crm-account-head">
                {avatarSrc ? (
                  <img className="crm-account-avatar" src={avatarSrc} alt="" />
                ) : (
                  <div className="crm-account-avatar crm-account-avatar--placeholder" aria-hidden="true">
                    {String(title).slice(0, 1).toUpperCase()}
                  </div>
                )}
                <div className="crm-account-meta">
                  <div className="crm-item-header">
                    <h5 className="crm-item-title">{title}</h5>
                    <span className={`crm-status ${statusMeta.className}`}>
                      {statusMeta.label}
                    </span>
                  </div>
                  <p className="crm-item-subtitle">{account.bio || 'Нет описания'}</p>
                  <p className="crm-item-subtitle">
                    {account.phone_number || account.username || `#${account.id}`}
                  </p>
                </div>
              </div>
              <p className="crm-item-subtitle">
                {account.is_spamblocked ? <span className="crm-status crm-status--spamblock">СПАМБЛОК</span> : null}
                {account.is_spamblocked ? ' · ' : ''}
                {account.is_banned ? 'Бан · ' : ''}
                {WARMUP_STATUS_LABELS[account.warmup_status] || ''}
                {account.warmup_status && account.warmup_status !== 'idle' ? ' · ' : ''}
                {account.proxy_label ? `${account.proxy_label} · ` : ''}
                {account.risk_score !== null && account.trust_score !== null
                  ? `Risk ${account.risk_score} · Trust ${account.trust_score} · `
                  : ''}
                {account.daily_messages_sent} / {account.max_daily_messages_per_account ?? '—'} сообщений сегодня
              </p>
              <span className="crm-date">
                {account.last_used_at
                  ? `Последнее использование ${new Date(account.last_used_at).toLocaleString()}`
                  : 'Ещё не использовался'}
                {account.added_at ? ` · добавлен ${new Date(account.added_at).toLocaleString()}` : ''}
                {account.spamblock_checked_at
                  ? ` · спамблок ${new Date(account.spamblock_checked_at).toLocaleString()}`
                  : ''}
              </span>
              <div className="form-group">
                <label htmlFor={`name-${account.id}`}>Имя</label>
                <input
                  id={`name-${account.id}`}
                  type="text"
                  value={nameDrafts[account.id] ?? account.display_name ?? ''}
                  onChange={(e) => setNameDrafts((prev) => ({ ...prev, [account.id]: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor={`bio-${account.id}`}>Описание</label>
                <textarea
                  id={`bio-${account.id}`}
                  rows={2}
                  maxLength={140}
                  value={bioDrafts[account.id] ?? account.bio ?? ''}
                  onChange={(e) => setBioDrafts((prev) => ({ ...prev, [account.id]: e.target.value }))}
                  placeholder="О себе в Telegram"
                />
              </div>
              <div className="form-group">
                <label htmlFor={`avatar-${account.id}`}>Аватар</label>
                <CustomFileButton
                  id={`avatar-${account.id}`}
                  accept="image/*"
                  onFile={(file) => handleAccountAvatar(account, file)}
                >
                  Выбрать фото
                </CustomFileButton>
              </div>
              <div className="form-group">
                <label htmlFor={`roles-${account.id}`}>Функции</label>
                <CustomSelect
                  id={`roles-${account.id}`}
                  multiple
                  value={account.roles || []}
                  options={ACCOUNT_ROLE_OPTIONS}
                  placeholder="Молчит"
                  onChange={(e) => handleRolesChange(account.id, e.target.value)}
                />
                <span className="form-hint">Пустой список — аккаунт ничего не делает.</span>
              </div>
              <div className="form-group">
                <label htmlFor={`class-${account.id}`}>Класс</label>
                <CustomSelect
                  id={`class-${account.id}`}
                  value={account.assigned_class}
                  options={ACCOUNT_CLASSES.filter((c) => c.value)}
                  onChange={(e) => handleClassChange(account.id, e.target.value)}
                />
              </div>
              <span className={`crm-status ${CLASS_STATUS[account.assigned_class] || ''}`}>
                {(account.roles || []).map((role) => ACCOUNT_ROLE_LABELS[role] || role).join(' · ')
                  || 'Молчит'}
              </span>
              <div className="settings-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  disabled={checkingSpamblockId === account.id || account.status === 'empty'}
                  onClick={() => handleCheckSpamblock(account)}
                >
                  {checkingSpamblockId === account.id ? 'Проверяем...' : 'Проверить спамблок'}
                </button>
                <button
                  type="button"
                  className="btn btn-black"
                  disabled={savingNameId === account.id}
                  onClick={() => handleSaveProfile(account)}
                >
                  {savingNameId === account.id ? 'Сохранение...' : 'Сохранить'}
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-danger"
                  onClick={() => handleDeleteAccount(account)}
                >
                  Удалить
                </button>
              </div>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default CustomAutomationAccountsPage;
