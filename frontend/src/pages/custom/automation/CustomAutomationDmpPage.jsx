import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectDashboard.css';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customAccountManager.css';

const DMP_IMPORT_TYPES = [
  { value: 'website', label: 'Посетители сайта' },
  { value: 'competitors', label: 'Клиенты конкурентов' },
  { value: 'phones', label: 'По номерам телефонов' },
  { value: 'other', label: 'Другое' },
];

const IMPORT_STATUS_LABELS = {
  pending: 'в очереди',
  processing: 'ждём номера',
  completed: 'получен',
  failed: 'ошибка',
};

const LEAD_STATUS_LABELS = {
  new: 'новый',
  warming: 'прогрев',
  qualified: 'квалифицирован',
  transferred: 'передан',
  processing: 'в обработке',
  converted: 'уже клиент',
  lost: 'дубль',
  spam: 'спам',
};

const deliveryLabel = (lead) => {
  if (lead.bot_notified_at && lead.sheets_synced_at) {
    return 'бот и таблица';
  }
  if (lead.bot_notified_at) {
    return 'в боте';
  }
  if (lead.sheets_synced_at) {
    return 'в таблице';
  }
  if (lead.status === 'transferred') {
    return 'ждёт доставку';
  }
  return '—';
};

const SASHA_STATUS_LABELS = {
  queued: 'в очереди',
  uploaded: 'ушло в Сашу',
  skipped: 'пропущен',
  called: 'был звонок',
  connected: 'дозвон',
  committed: 'лид',
  rejected: 'отказ',
  no_answer: 'недозвон',
  failed: 'ошибка отправки',
};

const formatDate = (value) => {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleString('ru-RU');
  } catch {
    return String(value);
  }
};

const CustomAutomationDmpPage = () => {
  const { id } = useParams();
  const [imports, setImports] = useState([]);
  const [importsTotal, setImportsTotal] = useState(0);
  const [leads, setLeads] = useState([]);
  const [leadsTotal, setLeadsTotal] = useState(0);
  const [warnings, setWarnings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [form, setForm] = useState({
    importType: 'website',
    sourceUrl: '',
    requestedCount: 100,
  });

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [importsData, leadsData, validation] = await Promise.all([
        customService.getDmpImports(id, { limit: 50, offset: 0 }),
        customService.getLeads(id, { source: 'dmp_one', limit: 100, offset: 0 }),
        customService.getAutomationValidation(id).catch(() => null),
      ]);
      setImports(importsData.items || []);
      setImportsTotal(importsData.total ?? (importsData.items || []).length);
      setLeads(leadsData.items || []);
      setLeadsTotal(leadsData.total ?? (leadsData.items || []).length);
      setWarnings(validation?.warnings || []);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить DMP');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setIsCreating(true);
    setMessage(null);
    setError(null);
    if (!String(form.sourceUrl || '').trim()) {
      setError('Укажите источник: сайт, URL или список номеров');
      setIsCreating(false);
      return;
    }
    try {
      await customService.createDmpOrder(id, {
        importType: form.importType,
        sourceUrl: form.sourceUrl,
        requestedCount: Number(form.requestedCount) || 100,
      });
      setMessage('Заказ в DMP.one создан');
      setForm({ importType: 'website', sourceUrl: '', requestedCount: 100 });
      await loadAll();
    } catch (err) {
      setError(err.message || 'Не удалось создать заказ');
    } finally {
      setIsCreating(false);
    }
  };

  const handlePoll = async () => {
    setIsPolling(true);
    setMessage(null);
    setError(null);
    try {
      const result = await customService.runDmpPoll(id);
      const processed = result.imports_processed || 0;
      const created = result.leads_created || 0;
      const retried = result.leads_retried || 0;
      if (result.reason === 'orders_disabled') {
        setMessage(`Модуль выключен: заказы не опрашивались. Повторно проверено номеров: ${retried}.`);
      } else {
        setMessage(`Готово. Заказов: ${processed}, новых номеров: ${created}, повторно: ${retried}.`);
      }
      await loadAll();
    } catch (err) {
      setError(err.message || 'Опрос не удался');
    } finally {
      setIsPolling(false);
    }
  };

  const totals = imports.reduce(
    (acc, item) => {
      acc.requested += item.requested_count || 0;
      acc.received += item.received_count || 0;
      acc.purchased += item.purchased_count || 0;
      acc.cost += item.cost_rub || 0;
      return acc;
    },
    { requested: 0, received: 0, purchased: 0, cost: 0 },
  );

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Дашборд DMP</h1>
          <p>
            DMP.one сам присылает номера JSON-ом на webhook. Телефон уходит в Sasha AI, без телефона — в аккаунт перехвата или сразу в бота.
          </p>
        </div>
        <div className="settings-actions">
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_SASHA(id)} className="acc-btn acc-btn--ghost">
            Прозвон Sasha AI
          </Link>
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_CONNECTION(id)} className="acc-btn acc-btn--ghost">
            Подключение
          </Link>
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_SETTINGS(id)} className="acc-btn acc-btn--ghost">
            Настройки
          </Link>
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}
      {warnings.length ? (
        <div className="ubt-panel">
          <h2>Контур ещё не готов</h2>
          <ul>
            {warnings.map((item) => <li key={item} className="form-hint">{item}</li>)}
          </ul>
        </div>
      ) : null}

      <div className="ubt-kpi-grid">
        <div className="ubt-kpi">
          <strong>{leadsTotal}</strong>
          <span>Номеров в базе</span>
        </div>
        <div className="ubt-kpi">
          <strong>{totals.purchased}</strong>
          <span>Куплено</span>
        </div>
        <div className="ubt-kpi">
          <strong>{totals.received}</strong>
          <span>Получено</span>
        </div>
        <div className="ubt-kpi">
          <strong>{totals.cost.toFixed(0)} ₽</strong>
          <span>Расход</span>
        </div>
      </div>
      {importsTotal > imports.length ? (
        <p className="form-hint">Куплено, получено и расход здесь по последним приёмам на экране. «Номеров в базе» считает все контакты.</p>
      ) : null}

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Список номеров</h2>
          {leadsTotal > leads.length ? <p>Показаны последние {leads.length} из {leadsTotal}</p> : null}
        </div>
        {isLoading ? (
          <p className="ubt-empty">Загрузка...</p>
        ) : leads.length === 0 ? (
          <p className="ubt-empty">Номеров пока нет — создайте заказ или дождитесь вебхука.</p>
        ) : (
          <table className="ubt-table">
            <thead>
              <tr>
                <th>Номер</th>
                <th>Имя</th>
                <th>Статус</th>
                <th>Доставка</th>
                <th>Sasha AI</th>
                <th>Прогрев</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(id, lead.id)}>
                      {lead.contact_value || `Лид #${lead.id}`}
                    </Link>
                  </td>
                  <td>{lead.full_name || '—'}</td>
                  <td>{LEAD_STATUS_LABELS[lead.status] || lead.status || '—'}</td>
                  <td>{deliveryLabel(lead)}</td>
                  <td>{SASHA_STATUS_LABELS[lead.sasha_status] || lead.sasha_status || '—'}</td>
                  <td>
                    {lead.sasha_lead_quality == null
                      ? '—'
                      : `${lead.sasha_lead_quality}/10${lead.sasha_is_commit ? ' · лид' : ''}`}
                  </td>
                  <td>{formatDate(lead.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Приёмы из DMP.one</h2>
          {importsTotal > imports.length ? <p>Показаны последние {imports.length} из {importsTotal}</p> : null}
        </div>
        {isLoading ? (
          <p className="ubt-empty">Загрузка...</p>
        ) : imports.length === 0 ? (
          <p className="ubt-empty">Пока пусто. Вставьте webhook в кабинете DMP.one и отправьте тестовый визит.</p>
        ) : (
          <table className="ubt-table">
            <thead>
              <tr>
                <th>Когда</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Запрошено</th>
                <th>Получено</th>
                <th>Куплено</th>
                <th>Расход</th>
              </tr>
            </thead>
            <tbody>
              {imports.map((item) => (
                <tr key={item.id}>
                  <td>{formatDate(item.created_at)}</td>
                  <td>{DMP_IMPORT_TYPES.find((row) => row.value === item.import_type)?.label || item.import_type || '—'}</td>
                  <td>{IMPORT_STATUS_LABELS[item.status] || item.status || '—'}</td>
                  <td>{item.requested_count ?? '—'}</td>
                  <td>{item.received_count ?? '—'}</td>
                  <td>{item.purchased_count ?? '—'}</td>
                  <td>{item.cost_rub == null ? '—' : `${Math.round(item.cost_rub)} ₽`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Заказ через API</h2>
          <p>Основной путь — webhook из кабинета DMP.one. Этот заказ нужен, только если на сервере заданы ключ и адрес API DMP.one.</p>
        </div>
        <form onSubmit={handleCreate}>
          <div className="form-group">
            <label htmlFor="dmp-type">Тип импорта</label>
            <CustomSelect
              id="dmp-type"
              value={form.importType}
              options={DMP_IMPORT_TYPES}
              onChange={(e) => setForm((f) => ({ ...f, importType: e.target.value }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="dmp-source">Источник (URL, сайт, номера)</label>
            <input
              id="dmp-source"
              type="text"
              placeholder="https://example.com"
              value={form.sourceUrl}
              onChange={(e) => setForm((f) => ({ ...f, sourceUrl: e.target.value }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="dmp-count">Количество</label>
            <input
              id="dmp-count"
              type="number"
              min={1}
              value={form.requestedCount}
              onChange={(e) => setForm((f) => ({ ...f, requestedCount: e.target.value }))}
            />
          </div>
          <div className="settings-actions">
            <button type="submit" disabled={isCreating} className="btn btn-black">
              {isCreating ? 'Создание...' : 'Создать заказ'}
            </button>
            <button type="button" onClick={handlePoll} disabled={isPolling} className="btn btn-outline">
              {isPolling ? '...' : 'Опросить результаты'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CustomAutomationDmpPage;
