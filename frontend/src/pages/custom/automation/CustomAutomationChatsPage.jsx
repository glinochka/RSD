import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { parseTelegramChatRef } from '../../../utils/telegramChatLink';
import CustomAutomationChatDiscoveryPage from './CustomAutomationChatDiscoveryPage';
import { CHAT_TYPE_LABELS } from './activityLabels';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

const JOIN_STATUSES = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'В очереди' },
  { value: 'joining', label: 'Вступаем' },
  { value: 'joined', label: 'Вступили' },
  { value: 'rate_limited', label: 'Rate limit' },
  { value: 'error', label: 'Ошибка' },
  { value: 'banned', label: 'Бан' },
];

const JOIN_STATUS_LABELS = Object.fromEntries(
  JOIN_STATUSES.filter((item) => item.value).map((item) => [item.value, item.label])
);

const ACTIVITY_OPTIONS = [
  { value: '', label: 'Любая активность' },
  { value: '1', label: 'За час' },
  { value: '6', label: 'За 6 часов' },
  { value: '24', label: 'За сутки' },
  { value: '72', label: 'За 3 дня' },
  { value: '168', label: 'За неделю' },
  { value: '720', label: 'За 30 дней' },
];

const COMMENTS_OPTIONS = [
  { value: '', label: 'Все' },
  { value: 'open', label: 'Комментарии открыты' },
  { value: 'closed', label: 'Комментарии закрыты' },
  { value: 'unchecked', label: 'Не проверены' },
];

const PAGE_SIZE = 50;

function chatTypeLabel(chat) {
  const key = (chat.chat_type || '').toLowerCase();
  return CHAT_TYPE_LABELS[key] || (key ? chat.chat_type : 'Чат');
}

function formatActivity(iso) {
  if (!iso) {
    return 'нет данных';
  }
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) {
    return `${mins} мин.`;
  }
  const hours = Math.round(mins / 60);
  if (hours < 24) {
    return `${hours} ч.`;
  }
  return `${Math.round(hours / 24)} дн.`;
}

function commentsLabel(chat) {
  if (chat.comments_open === true) {
    return 'комментарии открыты';
  }
  if (chat.comments_open === false) {
    return 'комментарии закрыты';
  }
  return 'комментарии не проверены';
}

const CustomAutomationChatsPage = ({ defaultTab = 'list' }) => {
  const { id } = useParams();
  const [chats, setChats] = useState([]);
  const [total, setTotal] = useState(0);
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [tab, setTab] = useState(defaultTab);
  const [showForm, setShowForm] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [inviteLink, setInviteLink] = useState('');
  const [offset, setOffset] = useState(0);
  const [inspectOn, setInspectOn] = useState(false);
  const [inspectStatus, setInspectStatus] = useState(null);
  const [filters, setFilters] = useState({
    joinStatus: '',
    comments: '',
    activityHours: '',
    minMembers: '',
    maxMembers: '',
  });

  const parsedLink = useMemo(() => parseTelegramChatRef(inviteLink), [inviteLink]);

  const loadChats = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getChats(id, {
        joinStatus: filters.joinStatus || undefined,
        commentsOpen: filters.comments === 'open' ? true : filters.comments === 'closed' ? false : undefined,
        commentsUnchecked: filters.comments === 'unchecked' || undefined,
        minMembers: filters.minMembers === '' ? undefined : Number(filters.minMembers),
        maxMembers: filters.maxMembers === '' ? undefined : Number(filters.maxMembers),
        activityWithinHours: filters.activityHours || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setChats(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load chats');
    } finally {
      setIsLoading(false);
    }
  }, [id, filters, offset]);

  const loadJobs = useCallback(async () => {
    try {
      const data = await customService.getImportJobs(id, { limit: 10, offset: 0 });
      setJobs(data.items || []);
    } catch {
      // ignore
    }
  }, [id]);

  useEffect(() => {
    loadChats();
    loadJobs();
  }, [loadChats, loadJobs]);

  useEffect(() => {
    if (!inspectOn || !id) {
      return undefined;
    }
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const data = await customService.getChatInspectStatus(id);
        if (cancelled) {
          return;
        }
        setInspectStatus(data);
        if (data.status === 'running') {
          timer = window.setTimeout(poll, 3000);
          return;
        }
        await loadChats();
      } catch {
        if (!cancelled) {
          timer = window.setTimeout(poll, 4000);
        }
      }
    };
    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [inspectOn, id, loadChats]);

  const handleImport = async (file) => {
    if (!file) {
      return;
    }
    setIsImporting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await customService.bulkImportChats(id, file);
      const duplicates = result.duplicate_rows || 0;
      setMessage(
        `Импорт: новых ${result.processed_rows} из ${result.total_rows}`
          + (duplicates ? `, дубликатов ${duplicates}` : '')
          + `, ошибок ${result.error_rows}`,
      );
      setShowFilters(true);
      setOffset(0);
      await loadChats();
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Import failed');
    } finally {
      setIsImporting(false);
    }
  };

  const handleInspectToggle = async (checked) => {
    setInspectOn(checked);
    if (!checked) {
      return;
    }
    setError(null);
    try {
      const force = Boolean(inspectStatus && inspectStatus.status === 'completed');
      const started = await customService.inspectChatComments(id, force);
      setInspectStatus(started);
      setShowFilters(true);
    } catch (err) {
      setInspectOn(false);
      setError(err.message || 'Не удалось начать проверку комментариев');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!parsedLink.ok) {
      setError(parsedLink.error || 'Некорректная ссылка');
      return;
    }
    setIsCreating(true);
    setError(null);
    setMessage(null);
    try {
      const created = await customService.createChat(id, { invite_link: inviteLink.trim() });
      setShowForm(false);
      setInviteLink('');
      const foundTitle = created.title || created.invite_link;
      setMessage(`Нашли ${chatTypeLabel(created).toLowerCase()}: ${foundTitle}. Юзерботы вступают в фоне`);
      await loadChats();
    } catch (err) {
      setError(err.message || 'Failed to create chat');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (chatId) => {
    if (!window.confirm('Удалить чат?')) {
      return;
    }
    try {
      await customService.deleteChat(id, chatId);
      await loadChats();
    } catch (err) {
      setError(err.message || 'Failed to delete chat');
    }
  };

  const handleJoin = async () => {
    setIsJoining(true);
    setMessage(null);
    try {
      await customService.runChatJoin(id);
      setMessage('Вступление в чаты запущено в фоне');
    } catch (err) {
      setError(err.message || 'Join failed');
    } finally {
      setIsJoining(false);
    }
  };

  const handlePauseToggle = async (chat) => {
    const nextActive = !(chat.is_active && chat.mode !== 'inactive');
    try {
      await customService.updateChatNeurocommentingConfig(id, chat.id, { isActive: nextActive });
      await loadChats();
      setMessage(nextActive ? 'Чат снова в работе' : 'Чат на паузе');
    } catch (err) {
      setError(err.message || 'Failed to update chat');
    }
  };

  const inputClass = parsedLink.empty
    ? ''
    : parsedLink.ok
      ? 'input-valid'
      : 'input-invalid';

  const pageFrom = total === 0 ? 0 : offset + 1;
  const pageTo = Math.min(offset + chats.length, total);

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Чаты</h1>
          <p className="crm-subtitle">
            Модули из Настроек работают сразу во всех вступивших чатах и каналах. Здесь можно только поставить чат на паузу.
          </p>
        </div>
        <div className="crm-stats">
          <div className="crm-stat">
            <span className="crm-stat-value">{total}</span>
            <span className="crm-stat-label">Всего</span>
          </div>
        </div>
      </div>
      <div className="crm-tabs">
        <button type="button" className={`crm-tab ${tab === 'list' ? 'crm-tab--active' : ''}`} onClick={() => setTab('list')}>
          Список
        </button>
        <button type="button" className={`crm-tab ${tab === 'discovery' ? 'crm-tab--active' : ''}`} onClick={() => setTab('discovery')}>
          Автопоиск
        </button>
      </div>
      {tab === 'discovery' ? <CustomAutomationChatDiscoveryPage /> : null}
      {tab !== 'list' ? null : (
        <>
          <div className="settings-actions">
            <button type="button" onClick={() => setShowForm((s) => !s)} className="btn btn-outline">
              {showForm ? 'Скрыть форму' : 'Добавить чат'}
            </button>
            <CustomFileButton
              accept=".csv,.xlsx,.xls"
              variant="black"
              busy={isImporting}
              onFile={handleImport}
            >
              {isImporting ? 'Импорт...' : 'Импорт Excel'}
            </CustomFileButton>
            <button type="button" onClick={() => setShowFilters((s) => !s)} className="btn btn-outline">
              {showFilters ? 'Скрыть фильтр' : 'Фильтр'}
            </button>
            <button type="button" onClick={handleJoin} disabled={isJoining} className="btn btn-outline">
              {isJoining ? '...' : 'Вступить сейчас'}
            </button>
          </div>

          {message ? <p className="crm-flash">{message}</p> : null}
          {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

          {showForm ? (
            <form onSubmit={handleCreate} className="settings-section">
              <h3 className="settings-section-title">Новый чат</h3>
              <div className="form-group">
                <label htmlFor="chat-invite">Ссылка, @username или имя</label>
                <input
                  id="chat-invite"
                  type="text"
                  value={inviteLink}
                  className={inputClass}
                  placeholder="https://t.me/name, t.me/name, @name или name"
                  onChange={(e) => setInviteLink(e.target.value)}
                  autoComplete="off"
                />
                {parsedLink.empty ? (
                  <span className="form-hint">Название и тип подтянутся сами после того, как юзербот найдёт чат или канал</span>
                ) : parsedLink.ok ? (
                  <span className="form-hint form-hint--ok">{parsedLink.canonical}</span>
                ) : (
                  <span className="form-hint form-hint--error">{parsedLink.error}</span>
                )}
              </div>
              <div className="settings-actions">
                <button type="submit" className="btn btn-black" disabled={isCreating || !parsedLink.ok}>
                  {isCreating ? 'Ищем...' : 'Добавить'}
                </button>
              </div>
            </form>
          ) : null}

          {showFilters ? (
            <div className="settings-section">
              <h3 className="settings-section-title">Фильтр</h3>
              <FeatureToggle
                title="Проверить комментарии"
                description="Все аккаунты параллельно смотрят, открыты ли комментарии. В чаты ничего не пишут."
                checked={inspectOn}
                onChange={handleInspectToggle}
              />
              {inspectStatus?.status === 'running' ? (
                <p className="form-hint">
                  Проверено {inspectStatus.checked || 0} из {inspectStatus.total || 0}
                </p>
              ) : null}
              {inspectStatus?.status === 'completed' ? (
                <p className="form-hint">
                  Открыты {inspectStatus.comments_open || 0} · закрыты {inspectStatus.comments_closed || 0}
                </p>
              ) : null}
              {inspectStatus?.error ? (
                <p className="form-hint form-hint--error">{inspectStatus.error}</p>
              ) : null}
              <div className="activity-filters">
                <div className="form-group">
                  <label htmlFor="chat-filter">Статус вступления</label>
                  <CustomSelect
                    id="chat-filter"
                    value={filters.joinStatus}
                    options={JOIN_STATUSES}
                    onChange={(e) => {
                      setOffset(0);
                      setFilters((f) => ({ ...f, joinStatus: e.target.value }));
                    }}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chat-comments">Комментарии</label>
                  <CustomSelect
                    id="chat-comments"
                    value={filters.comments}
                    options={COMMENTS_OPTIONS}
                    onChange={(e) => {
                      setOffset(0);
                      setFilters((f) => ({ ...f, comments: e.target.value }));
                    }}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chat-activity">Последняя активность</label>
                  <CustomSelect
                    id="chat-activity"
                    value={filters.activityHours}
                    options={ACTIVITY_OPTIONS}
                    onChange={(e) => {
                      setOffset(0);
                      setFilters((f) => ({ ...f, activityHours: e.target.value }));
                    }}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chat-min-members">Подписчики от</label>
                  <input
                    id="chat-min-members"
                    type="number"
                    min="0"
                    value={filters.minMembers}
                    onChange={(e) => {
                      setOffset(0);
                      setFilters((f) => ({ ...f, minMembers: e.target.value }));
                    }}
                    placeholder="0"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chat-max-members">Подписчики до</label>
                  <input
                    id="chat-max-members"
                    type="number"
                    min="0"
                    value={filters.maxMembers}
                    onChange={(e) => {
                      setOffset(0);
                      setFilters((f) => ({ ...f, maxMembers: e.target.value }));
                    }}
                    placeholder="без лимита"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="settings-section">
              <div className="form-group">
                <label htmlFor="chat-filter-basic">Статус вступления</label>
                <CustomSelect
                  id="chat-filter-basic"
                  value={filters.joinStatus}
                  options={JOIN_STATUSES}
                  onChange={(e) => {
                    setOffset(0);
                    setFilters((f) => ({ ...f, joinStatus: e.target.value }));
                  }}
                />
              </div>
            </div>
          )}

          {isLoading ? (
            <div className="crm-empty-list"><p>Загрузка...</p></div>
          ) : chats.length === 0 ? (
            <div className="crm-empty-list">
              <p>Нет чатов</p>
              <span>Добавьте вручную или импортируйте Excel.</span>
            </div>
          ) : (
            <div className="crm-list">
              {chats.map((chat) => (
                <div key={chat.id} className="crm-item">
                  <div className="crm-item-header">
                    <h5 className="crm-item-title">{chat.title || `Chat #${chat.id}`}</h5>
                    <span className="crm-status">{JOIN_STATUS_LABELS[chat.join_status] || chat.join_status}</span>
                  </div>
                  <p className="crm-item-subtitle">{chat.invite_link || chat.external_chat_id || '-'}</p>
                  <p className="crm-item-subtitle">
                    {chatTypeLabel(chat)}
                    {chat.is_active && chat.mode !== 'inactive' ? ' · в работе' : ' · пауза'}
                    {chat.members_count != null ? ` · ${chat.members_count} подп.` : ''}
                    {` · ${formatActivity(chat.last_activity_at)}`}
                    {` · ${commentsLabel(chat)}`}
                  </p>
                  {chat.last_join_error ? (
                    <p className="crm-item-subtitle form-hint--error">{chat.last_join_error}</p>
                  ) : null}
                  <div className="crm-item-actions">
                    <button type="button" onClick={() => handlePauseToggle(chat)} className="btn btn-outline">
                      {chat.is_active && chat.mode !== 'inactive' ? 'Пауза' : 'Включить'}
                    </button>
                    <button type="button" onClick={() => handleDelete(chat.id)} className="btn btn-outline">Удалить</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {total > PAGE_SIZE ? (
            <div className="settings-actions">
              <button
                type="button"
                className="btn btn-outline"
                disabled={offset === 0}
                onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
              >
                Назад
              </button>
              <span className="form-hint">{pageFrom}–{pageTo} из {total}</span>
              <button
                type="button"
                className="btn btn-outline"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((value) => value + PAGE_SIZE)}
              >
                Дальше
              </button>
            </div>
          ) : null}

          {jobs.length > 0 ? (
            <div className="settings-section">
              <h3 className="settings-section-title">Импорты</h3>
              <div className="crm-list">
                {jobs.map((job) => (
                  <div key={job.id} className="crm-item">
                    <div className="crm-item-header">
                      <h5 className="crm-item-title">{job.file_name}</h5>
                      <span className="crm-status">{job.status}</span>
                    </div>
                    <p className="crm-item-subtitle">
                      {job.processed_rows} / {job.total_rows}
                      {job.duplicate_rows ? ` · дубликатов ${job.duplicate_rows}` : ''}
                      {` · ошибок ${job.error_rows}`}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
};

export default CustomAutomationChatsPage;
