import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService, { mediaUrl } from '../../../services/customService';
import CustomBulkProfileForm from './CustomBulkProfileForm';
import CustomAccountConnectForm from './CustomAccountConnectForm';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

const ACCOUNT_CLASSES = [
  { value: '', label: 'Все классы' },
  { value: 'one_day', label: 'Однодневный' },
  { value: 'mid', label: 'Средний' },
  { value: 'trusted', label: 'Доверенный' },
  { value: 'shilling', label: 'Шиллинг' },
];

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
  const [accounts, setAccounts] = useState([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [classifyMessage, setClassifyMessage] = useState(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const [banStats, setBanStats] = useState(null);
  const [healthCheckMessage, setHealthCheckMessage] = useState(null);
  const [isHealthChecking, setIsHealthChecking] = useState(false);
  const [savingNameId, setSavingNameId] = useState(null);
  const [nameDrafts, setNameDrafts] = useState({});
  const [filters, setFilters] = useState({
    status: '',
    accountClass: '',
    search: '',
  });

  const loadAccounts = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationAccounts(id, {
        status: filters.status || undefined,
        accountClass: filters.accountClass || undefined,
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
  }, [id, filters.status, filters.accountClass, filters.search]);

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

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadAccounts();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) {
      return;
    }
    setUploadError(null);
    setUploadSuccess(null);
    setIsUploading(true);
    try {
      const result = await customService.bulkUploadAccounts(id, file, filters.accountClass || 'one_day');
      setUploadSuccess(
        `Загружено: ${result.created}, пропущено: ${result.skipped}, ошибок: ${result.errors.length}`,
      );
      await loadAccounts();
    } catch (err) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
      e.target.value = '';
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

  const handleSaveName = async (account) => {
    const name = (nameDrafts[account.id] ?? account.display_name ?? '').trim();
    if (!name) {
      setError('Имя не может быть пустым');
      return;
    }
    setSavingNameId(account.id);
    setError(null);
    try {
      await customService.updateAccount(id, account.id, { displayName: name });
      await loadAccounts();
    } catch (err) {
      setError(err.message || 'Не удалось сменить имя');
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
      await customService.bulkUpdateProfiles(id, {
        avatar: file,
        accountIds: [account.id],
      });
      setUploadSuccess('Аватар в очереди на обновление. Обновите список через минуту.');
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

  const distribution = accounts.reduce((acc, a) => {
    acc[a.assigned_class] = (acc[a.assigned_class] || 0) + 1;
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
          <label className="btn btn-black">
            <input
              type="file"
              accept=".zip,.csv,.session"
              onChange={handleFileChange}
              disabled={isUploading}
              style={{ display: 'none' }}
            />
            {isUploading ? 'Загрузка...' : 'Загрузить ZIP / CSV / .session'}
          </label>
        </div>
      </div>

      {classifyMessage ? <p className="crm-flash">{classifyMessage}</p> : null}
      {healthCheckMessage ? <p className="crm-flash">{healthCheckMessage}</p> : null}
      {uploadSuccess ? <p className="crm-flash">{uploadSuccess}</p> : null}
      {uploadError ? <p className="crm-flash crm-flash--error">{uploadError}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

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
          {ACCOUNT_CLASSES.filter((c) => c.value).map((c) => (
            <div key={c.value} className="crm-stat">
              <span className="crm-stat-value">{distribution[c.value] || 0}</span>
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
            const avatarSrc = mediaUrl(account.avatar_url);
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
              </span>
              <div className="form-group">
                <label htmlFor={`name-${account.id}`}>Имя аккаунта</label>
                <input
                  id={`name-${account.id}`}
                  type="text"
                  value={nameDrafts[account.id] ?? account.display_name ?? ''}
                  onChange={(e) => setNameDrafts((prev) => ({ ...prev, [account.id]: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor={`avatar-${account.id}`}>Аватар</label>
                <input
                  id={`avatar-${account.id}`}
                  type="file"
                  accept="image/*"
                  onChange={(e) => {
                    const file = e.target.files && e.target.files[0];
                    handleAccountAvatar(account, file);
                    e.target.value = '';
                  }}
                />
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
                {ACCOUNT_CLASSES.find((c) => c.value === account.assigned_class)?.label || account.assigned_class}
              </span>
              <div className="settings-actions">
                <button
                  type="button"
                  className="btn btn-black"
                  disabled={savingNameId === account.id}
                  onClick={() => handleSaveName(account)}
                >
                  {savingNameId === account.id ? 'Сохранение...' : 'Сохранить имя'}
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
