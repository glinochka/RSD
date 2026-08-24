import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import CustomBulkProfileForm from './CustomBulkProfileForm';

const ACCOUNT_CLASSES = [
  { value: '', label: 'Все классы' },
  { value: 'one_day', label: 'Однодневный' },
  { value: 'mid', label: 'Средний' },
  { value: 'trusted', label: 'Доверенный' },
];

const CLASS_COLORS = {
  one_day: 'bg-yellow-100 text-yellow-700',
  mid: 'bg-blue-100 text-blue-700',
  trusted: 'bg-green-100 text-green-700',
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
    } catch (err) {
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
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <h1 className="text-2xl font-semibold">Аккаунты автоматизации</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handleHealthCheck}
            disabled={isHealthChecking}
            className="bg-emerald-600 text-white px-4 py-2 rounded hover:bg-emerald-700 disabled:opacity-50"
          >
            {isHealthChecking ? 'Проверка...' : 'Проверить аккаунты'}
          </button>
          <button
            onClick={handleBulkClassify}
            disabled={isClassifying}
            className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
          >
            {isClassifying ? 'Проверка...' : 'Переклассифировать все'}
          </button>
          <label className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 cursor-pointer disabled:opacity-50">
            <input
              type="file"
              accept=".zip,.csv,.session"
              onChange={handleFileChange}
              disabled={isUploading}
              className="hidden"
            />
            {isUploading ? 'Загрузка...' : 'Загрузить ZIP / CSV / .session'}
          </label>
        </div>
      </div>

      {classifyMessage && (
        <div className={classifyMessage.startsWith('В очереди') ? 'text-purple-600' : 'text-red-600'}>
          {classifyMessage}
        </div>
      )}

      {healthCheckMessage && (
        <div className="text-emerald-600">{healthCheckMessage}</div>
      )}

      {banStats && banStats.alert && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4">
          <div className="font-semibold">Внимание: высокий процент забаненных аккаунтов</div>
          <div className="text-sm">
            Забанено {banStats.banned} из {banStats.total} ({(banStats.banned_percent * 100).toFixed(0)}%).
            {' '}
            Рекомендуется пополнить пул или снизить активность.
          </div>
        </div>
      )}

      {(uploadSuccess || uploadError) && (
        <div className="space-y-2">
          {uploadSuccess && <div className="text-green-600">{uploadSuccess}</div>}
          {uploadError && <div className="text-red-600">{uploadError}</div>}
        </div>
      )}

      {accounts.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 flex flex-wrap gap-3">
          {ACCOUNT_CLASSES.filter((c) => c.value).map((c) => (
            <div key={c.value} className="flex items-center gap-2 text-sm">
              <span className={`inline-flex px-2 py-1 rounded text-xs ${CLASS_COLORS[c.value]}`}>
                {c.label}
              </span>
              <span className="font-medium">{distribution[c.value] || 0}</span>
            </div>
          ))}
        </div>
      )}

      <CustomBulkProfileForm automationId={id} onSuccess={loadAccounts} />

      <div className="bg-white rounded-lg shadow p-4">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            >
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Класс</label>
            <select
              value={filters.accountClass}
              onChange={(e) => setFilters((f) => ({ ...f, accountClass: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            >
              {ACCOUNT_CLASSES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Поиск</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={filters.search}
                onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
                placeholder="Телефон, username, имя"
                className="flex-1 border border-gray-300 rounded px-3 py-2"
              />
              <button
                type="submit"
                className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                Найти
              </button>
            </div>
          </div>
        </form>
      </div>

      {error && <div className="text-red-600">{error}</div>}

      <div className="text-sm text-gray-500">Всего: {total}</div>

      {isLoading ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : accounts.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          Нет аккаунтов. Загрузите ZIP с .session файлами или CSV с метаданными.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">ID</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Телефон / Username</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Класс</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Risk / Trust</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Суточный лимит</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Последнее использование</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Добавлен</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono">{account.id}</td>
                  <td className="px-4 py-3 text-sm">
                    <div>{account.phone_number || account.username || '-'}</div>
                    {account.display_name && (
                      <div className="text-xs text-gray-500">{account.display_name}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex px-2 py-1 rounded text-xs ${
                          CLASS_COLORS[account.assigned_class] || 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {account.assigned_class}
                      </span>
                      <select
                        value={account.assigned_class}
                        onChange={(e) => handleClassChange(account.id, e.target.value)}
                        className="text-xs border border-gray-300 rounded px-1 py-1"
                      >
                        {ACCOUNT_CLASSES.filter((c) => c.value).map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex flex-col gap-1">
                      <span
                        className={`inline-flex px-2 py-1 rounded text-xs ${
                          account.status === 'loaded'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}
                      >
                        {account.status === 'loaded' ? 'Загружено' : 'Пусто'}
                      </span>
                      {account.is_banned && (
                        <span className="inline-flex px-2 py-1 rounded text-xs bg-red-100 text-red-700">
                          Забанен
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {account.risk_score !== null && account.trust_score !== null ? (
                      <div className="text-xs">
                        <div>Risk: {account.risk_score}</div>
                        <div>Trust: {account.trust_score}</div>
                      </div>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="text-xs mb-1">
                      {account.daily_messages_sent} / {account.max_daily_messages_per_account ?? '—'}
                    </div>
                    <div className="w-24 h-2 bg-gray-200 rounded overflow-hidden">
                      <div
                        className="h-full bg-blue-500"
                        style={{
                          width: `${Math.min(
                            100,
                            ((account.daily_messages_sent || 0) / (account.max_daily_messages_per_account || 1)) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {account.last_used_at ? new Date(account.last_used_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(account.added_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default CustomAutomationAccountsPage;
