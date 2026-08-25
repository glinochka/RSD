import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import CustomAutomationChatDiscoveryPage from './CustomAutomationChatDiscoveryPage';
import { CHAT_MODE_OPTIONS } from './activityLabels';
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

const MODES = CHAT_MODE_OPTIONS;

function parseActivityHours(value) {
  if (!value || value.trim() === '') {
    return [];
  }
  return value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [start, end] = part.split('-').map((s) => parseInt(s.trim(), 10));
      return [start, end];
    })
    .filter(([start, end]) => Number.isFinite(start) && Number.isFinite(end));
}

function formatActivityHours(config) {
  const hours = config?.activity_hours || [];
  if (!Array.isArray(hours) || hours.length === 0) {
    return '';
  }
  return hours.map(([start, end]) => `${start}-${end}`).join(', ');
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
  const [tab, setTab] = useState(defaultTab);
  const [filter, setFilter] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    invite_link: '',
    title: '',
    description: '',
    chat_type: '',
  });
  const [editing, setEditing] = useState({});

  const loadChats = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getChats(id, { joinStatus: filter || undefined, limit: 50, offset: 0 });
      setChats(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load chats');
    } finally {
      setIsLoading(false);
    }
  }, [id, filter]);

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

  const handleImport = async (e) => {
    const file = e.target.files[0];
    if (!file) {
      return;
    }
    setIsImporting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await customService.bulkImportChats(id, file);
      setMessage(`Импорт завершён: ${result.processed_rows} из ${result.total_rows}, ошибок ${result.error_rows}`);
      await loadChats();
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Import failed');
    } finally {
      setIsImporting(false);
      e.target.value = '';
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await customService.createChat(id, form);
      setShowForm(false);
      setForm({ invite_link: '', title: '', description: '', chat_type: '' });
      await loadChats();
    } catch (err) {
      setError(err.message || 'Failed to create chat');
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

  const startEdit = (chat) => {
    const neuro = chat.neurocommenting_config || {};
    const disc = chat.discussion_config || {};
    setEditing({
      chatId: chat.id,
      mode: chat.mode || 'monitoring',
      max_per_day: neuro.max_per_day || 10,
      frequency_minutes: neuro.frequency_minutes || 60,
      activity_hours: formatActivityHours(disc),
      reply_probability: (disc.reply_probability ?? 0.3) * 100,
    });
  };

  const cancelEdit = () => {
    setEditing({});
  };

  const saveEdit = async (chatId) => {
    try {
      if (editing.mode === 'neurocommenting') {
        await customService.updateChatNeurocommentingConfig(id, chatId, {
          mode: editing.mode,
          neurocommentingConfig: {
            max_per_day: Number(editing.max_per_day) || 10,
            frequency_minutes: Number(editing.frequency_minutes) || 60,
          },
        });
      } else if (editing.mode === 'discussion') {
        await customService.updateChatDiscussionConfig(id, chatId, {
          mode: editing.mode,
          discussionConfig: {
            activity_hours: parseActivityHours(editing.activity_hours),
            reply_probability: (Number(editing.reply_probability) || 0) / 100,
          },
        });
      } else if (editing.mode === 'shilling') {
        await customService.updateChatShillingConfig(id, chatId, {
          mode: editing.mode,
          shillingConfig: {},
        });
      } else {
        await customService.updateChatNeurocommentingConfig(id, chatId, {
          mode: editing.mode,
          neurocommentingConfig: {},
        });
      }
      setEditing({});
      await loadChats();
      setMessage('Настройки чата сохранены');
    } catch (err) {
      setError(err.message || 'Failed to update chat config');
    }
  };

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Чаты</h1>
          <p className="crm-subtitle">Залейте Excel со ссылками — система сама вступает. Автопоиск, если списка нет.</p>
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
            <label className="btn btn-black">
              <input type="file" accept=".csv,.xlsx,.xls" onChange={handleImport} disabled={isImporting} style={{ display: 'none' }} />
              {isImporting ? 'Импорт...' : 'Импорт Excel'}
            </label>
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
                <label htmlFor="chat-invite">Ссылка или invite</label>
                <input
                  id="chat-invite"
                  type="text"
                  value={form.invite_link}
                  onChange={(e) => setForm((f) => ({ ...f, invite_link: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="chat-title">Название</label>
                <input
                  id="chat-title"
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="chat-description">Описание</label>
                <input
                  id="chat-description"
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="chat-type">Тип (channel/chat)</label>
                <input
                  id="chat-type"
                  type="text"
                  value={form.chat_type}
                  onChange={(e) => setForm((f) => ({ ...f, chat_type: e.target.value }))}
                />
              </div>
              <div className="settings-actions">
                <button type="submit" className="btn btn-black">Сохранить</button>
              </div>
            </form>
          ) : null}

          <div className="settings-section">
            <div className="form-group">
              <label htmlFor="chat-filter">Статус вступления</label>
              <CustomSelect
                id="chat-filter"
                value={filter}
                options={JOIN_STATUSES}
                onChange={(e) => setFilter(e.target.value)}
              />
            </div>
          </div>

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
                    <span className="crm-status">{chat.join_status}</span>
                  </div>
                  <p className="crm-item-subtitle">{chat.invite_link || chat.external_chat_id || '-'}</p>
                  {editing.chatId === chat.id ? (
                    <>
                      <div className="form-group">
                        <label htmlFor={`mode-${chat.id}`}>Режим</label>
                        <CustomSelect
                          id={`mode-${chat.id}`}
                          value={editing.mode}
                          options={MODES}
                          onChange={(e) => setEditing((ed) => ({ ...ed, mode: e.target.value }))}
                        />
                      </div>
                      {editing.mode === 'neurocommenting' ? (
                        <>
                          <div className="form-group">
                            <label htmlFor={`max-${chat.id}`}>max/день</label>
                            <input
                              id={`max-${chat.id}`}
                              type="number"
                              min={1}
                              value={editing.max_per_day}
                              onChange={(e) => setEditing((ed) => ({ ...ed, max_per_day: e.target.value }))}
                            />
                          </div>
                          <div className="form-group">
                            <label htmlFor={`freq-${chat.id}`}>частота (мин)</label>
                            <input
                              id={`freq-${chat.id}`}
                              type="number"
                              min={1}
                              value={editing.frequency_minutes}
                              onChange={(e) => setEditing((ed) => ({ ...ed, frequency_minutes: e.target.value }))}
                            />
                          </div>
                        </>
                      ) : null}
                      {editing.mode === 'discussion' ? (
                        <>
                          <div className="form-group">
                            <label htmlFor={`hours-${chat.id}`}>часы активности (9-18, 20-23)</label>
                            <input
                              id={`hours-${chat.id}`}
                              type="text"
                              placeholder="9-18, 20-23"
                              value={editing.activity_hours}
                              onChange={(e) => setEditing((ed) => ({ ...ed, activity_hours: e.target.value }))}
                            />
                          </div>
                          <div className="form-group">
                            <label htmlFor={`prob-${chat.id}`}>вероятность ответа (%)</label>
                            <input
                              id={`prob-${chat.id}`}
                              type="number"
                              min={0}
                              max={100}
                              value={editing.reply_probability}
                              onChange={(e) => setEditing((ed) => ({ ...ed, reply_probability: e.target.value }))}
                            />
                          </div>
                        </>
                      ) : null}
                      <div className="crm-item-actions">
                        <button type="button" onClick={() => saveEdit(chat.id)} className="btn btn-black">Сохранить</button>
                        <button type="button" onClick={cancelEdit} className="btn btn-outline">Отмена</button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="crm-item-subtitle">
                        {MODES.find((m) => m.value === chat.mode)?.label || chat.mode}
                        {chat.mode === 'neurocommenting'
                          ? ` · max/день ${chat.neurocommenting_config?.max_per_day || 10} · ${chat.neurocommenting_config?.frequency_minutes || 60} мин`
                          : ''}
                        {chat.mode === 'discussion'
                          ? ` · часы ${formatActivityHours(chat.discussion_config) || 'все'} · ${Math.round((chat.discussion_config?.reply_probability || 0) * 100)}%`
                          : ''}
                        {` · попыток ${chat.join_attempts}`}
                      </p>
                      <div className="crm-item-actions">
                        <button type="button" onClick={() => startEdit(chat)} className="btn btn-outline">Настроить</button>
                        <button type="button" onClick={() => handleDelete(chat.id)} className="btn btn-outline">Удалить</button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}

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
                      {job.processed_rows} / {job.total_rows} · ошибок {job.error_rows}
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
