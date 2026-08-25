import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import CustomBulkProfileForm from './CustomBulkProfileForm';
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
  { value: 'loaded', label: 'Загружено' },
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

  const distribution = accounts.reduce((acc, a) => {
    acc[a.assigned_class] = (acc[a.assigned_class] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Аккаунты</h1>
          <p className="crm-subtitle">Массовый залив сессий. Классификация пройдёт сама.</p>
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

      <p className="crm-subtitle">
        Класс «Шиллинг» только для парных диалогов: не комментинг, не ЛС. Нужны минимум два разных аккаунта — один юзербот сам себе не отвечает.
      </p>

      <CustomBulkProfileForm automationId={id} onSuccess={loadAccounts} />

      <form onSubmit={handleSearchSubmit} className="settings-section">
        <h3 className="settings-section-title">Фильтр</h3>
        <div className="form-group">
          <label htmlFor="acc-status">Статус</label>
          <select
            id="acc-status"
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
          >
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="acc-class">Класс</label>
          <select
            id="acc-class"
            value={filters.accountClass}
            onChange={(e) => setFilters((f) => ({ ...f, accountClass: e.target.value }))}
          >
            {ACCOUNT_CLASSES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
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
          <span>Загрузите ZIP с .session файлами или CSV с метаданными.</span>
        </div>
      ) : (
        <div className="crm-list">
          {accounts.map((account) => (
            <div key={account.id} className="crm-item">
              <div className="crm-item-header">
                <h5 className="crm-item-title">{account.phone_number || account.username || `Аккаунт #${account.id}`}</h5>
                <span className={`crm-status ${account.status === 'loaded' ? 'crm-status--confirmed' : 'crm-status--pending'}`}>
                  {account.status === 'loaded' ? 'Загружено' : 'Пусто'}
                </span>
              </div>
              {account.display_name ? <p className="crm-item-subtitle">{account.display_name}</p> : null}
              <p className="crm-item-subtitle">
                {account.is_banned ? 'Забанен · ' : ''}
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
                <label htmlFor={`class-${account.id}`}>Класс</label>
                <select
                  id={`class-${account.id}`}
                  value={account.assigned_class}
                  onChange={(e) => handleClassChange(account.id, e.target.value)}
                >
                  {ACCOUNT_CLASSES.filter((c) => c.value).map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <span className={`crm-status ${CLASS_STATUS[account.assigned_class] || ''}`}>
                {ACCOUNT_CLASSES.find((c) => c.value === account.assigned_class)?.label || account.assigned_class}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CustomAutomationAccountsPage;
