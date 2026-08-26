import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import customService from '../../../services/customService';
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

function chatTypeLabel(chat) {
  const key = (chat.chat_type || '').toLowerCase();
  return CHAT_TYPE_LABELS[key] || (key ? chat.chat_type : 'Чат');
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

  const handleImport = async (file) => {
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
                  <p className="crm-item-subtitle">
                    {chatTypeLabel(chat)}
                    {chat.is_active && chat.mode !== 'inactive' ? ' · в работе' : ' · пауза'}
                    {` · попыток ${chat.join_attempts}`}
                  </p>
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
