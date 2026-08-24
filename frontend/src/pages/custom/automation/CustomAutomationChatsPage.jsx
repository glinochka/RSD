import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

const JOIN_STATUSES = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'В очереди' },
  { value: 'joining', label: 'Вступаем' },
  { value: 'joined', label: 'Вступили' },
  { value: 'rate_limited', label: 'Rate limit' },
  { value: 'error', label: 'Ошибка' },
  { value: 'banned', label: 'Бан' },
];

const MODES = [
  { value: 'monitoring', label: 'Мониторинг' },
  { value: 'neurocommenting', label: 'Нейрокомментинг' },
  { value: 'discussion', label: 'Обсуждения' },
  { value: 'inactive', label: 'Неактивен' },
];

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

const CustomAutomationChatsPage = () => {
  const { id } = useParams();
  const [chats, setChats] = useState([]);
  const [total, setTotal] = useState(0);
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isNeurocommenting, setIsNeurocommenting] = useState(false);
  const [isDiscussing, setIsDiscussing] = useState(false);
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

  const handleMonitor = async () => {
    setIsMonitoring(true);
    setMessage(null);
    try {
      await customService.runChatMonitor(id);
      setMessage('Мониторинг чатов запущен в фоне');
    } catch (err) {
      setError(err.message || 'Monitor failed');
    } finally {
      setIsMonitoring(false);
    }
  };

  const handleRunNeurocommenting = async () => {
    setIsNeurocommenting(true);
    setMessage(null);
    try {
      await customService.runNeurocommenting(id);
      setMessage('Нейрокомментинг запущен в фоне');
    } catch (err) {
      setError(err.message || 'Neurocommenting failed');
    } finally {
      setIsNeurocommenting(false);
    }
  };

  const handleRunDiscussion = async () => {
    setIsDiscussing(true);
    setMessage(null);
    try {
      await customService.runDiscussion(id);
      setMessage('Обсуждения запущены в фоне');
    } catch (err) {
      setError(err.message || 'Discussion failed');
    } finally {
      setIsDiscussing(false);
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
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <h1 className="text-2xl font-semibold">Чаты и мониторинг</h1>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => setShowForm((s) => !s)}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 text-sm"
          >
            {showForm ? 'Скрыть форму' : '+ Добавить чат'}
          </button>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCOVERY(id)}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 text-sm"
          >
            Автопоиск
          </Link>
          <label className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 cursor-pointer text-sm">
            <input type="file" accept=".csv,.xlsx,.xls" onChange={handleImport} disabled={isImporting} className="hidden" />
            {isImporting ? 'Импорт...' : 'Импорт CSV / Excel'}
          </label>
          <button
            onClick={handleJoin}
            disabled={isJoining}
            className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50 text-sm"
          >
            {isJoining ? '...' : 'Вступить в чаты'}
          </button>
          <button
            onClick={handleMonitor}
            disabled={isMonitoring}
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50 text-sm"
          >
            {isMonitoring ? '...' : 'Запустить мониторинг'}
          </button>
          <button
            onClick={handleRunNeurocommenting}
            disabled={isNeurocommenting}
            className="bg-orange-600 text-white px-4 py-2 rounded hover:bg-orange-700 disabled:opacity-50 text-sm"
          >
            {isNeurocommenting ? '...' : 'Нейрокомментинг'}
          </button>
          <button
            onClick={handleRunDiscussion}
            disabled={isDiscussing}
            className="bg-teal-600 text-white px-4 py-2 rounded hover:bg-teal-700 disabled:opacity-50 text-sm"
          >
            {isDiscussing ? '...' : 'Обсуждения'}
          </button>
        </div>
      </div>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <input
            placeholder="Ссылка или invite"
            value={form.invite_link}
            onChange={(e) => setForm((f) => ({ ...f, invite_link: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2"
          />
          <input
            placeholder="Название чата"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2"
          />
          <input
            placeholder="Описание"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2"
          />
          <input
            placeholder="Тип (channel/chat)"
            value={form.chat_type}
            onChange={(e) => setForm((f) => ({ ...f, chat_type: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2"
          />
          <button type="submit" className="md:col-span-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
            Сохранить
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-3 mb-4">
          <label className="text-sm font-medium text-gray-700">Статус:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm"
          >
            {JOIN_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="text-sm text-gray-500 mb-2">Всего: {total}</div>
        {isLoading ? (
          <div className="text-gray-500">Загрузка...</div>
        ) : chats.length === 0 ? (
          <div className="text-gray-500 text-center py-6">Нет чатов. Добавьте вручную или импортируйте.</div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Название</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Ссылка / ID</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Режим</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Настройки</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Попытки</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Действия</th>
              </tr>
            </thead>
            <tbody>
              {chats.map((chat) => (
                <tr key={chat.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{chat.title || `Chat #${chat.id}`}</td>
                  <td className="px-4 py-3 text-sm font-mono truncate max-w-xs">
                    {chat.invite_link || chat.external_chat_id || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className="inline-flex px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">
                      {chat.join_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {editing.chatId === chat.id ? (
                      <select
                        value={editing.mode}
                        onChange={(e) => setEditing((ed) => ({ ...ed, mode: e.target.value }))}
                        className="border border-gray-300 rounded px-2 py-1 text-sm"
                      >
                        {MODES.map((m) => (
                          <option key={m.value} value={m.value}>{m.label}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="inline-flex px-2 py-1 rounded text-xs bg-blue-50 text-blue-700">
                        {MODES.find((m) => m.value === chat.mode)?.label || chat.mode}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {editing.chatId === chat.id ? (
                      <div className="flex flex-col gap-2">
                        {editing.mode === 'neurocommenting' ? (
                          <>
                            <label className="text-xs text-gray-500">max/день</label>
                            <input
                              type="number"
                              min={1}
                              value={editing.max_per_day}
                              onChange={(e) => setEditing((ed) => ({ ...ed, max_per_day: e.target.value }))}
                              className="border border-gray-300 rounded px-2 py-1 text-sm w-24"
                            />
                            <label className="text-xs text-gray-500">частота (мин)</label>
                            <input
                              type="number"
                              min={1}
                              value={editing.frequency_minutes}
                              onChange={(e) => setEditing((ed) => ({ ...ed, frequency_minutes: e.target.value }))}
                              className="border border-gray-300 rounded px-2 py-1 text-sm w-24"
                            />
                          </>
                        ) : editing.mode === 'discussion' ? (
                          <>
                            <label className="text-xs text-gray-500">часы активности (9-18, 20-23)</label>
                            <input
                              type="text"
                              placeholder="9-18, 20-23"
                              value={editing.activity_hours}
                              onChange={(e) => setEditing((ed) => ({ ...ed, activity_hours: e.target.value }))}
                              className="border border-gray-300 rounded px-2 py-1 text-sm w-40"
                            />
                            <label className="text-xs text-gray-500">вероятность ответа (%)</label>
                            <input
                              type="number"
                              min={0}
                              max={100}
                              value={editing.reply_probability}
                              onChange={(e) => setEditing((ed) => ({ ...ed, reply_probability: e.target.value }))}
                              className="border border-gray-300 rounded px-2 py-1 text-sm w-24"
                            />
                          </>
                        ) : (
                          <span className="text-xs text-gray-500">Нет настроек</span>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-gray-600">
                        {chat.mode === 'neurocommenting' ? (
                          <>
                            <div>max/день: {chat.neurocommenting_config?.max_per_day || 10}</div>
                            <div>частота: {chat.neurocommenting_config?.frequency_minutes || 60} мин</div>
                          </>
                        ) : chat.mode === 'discussion' ? (
                          <>
                            <div>часы: {formatActivityHours(chat.discussion_config) || 'все'}</div>
                            <div>вероятность: {Math.round((chat.discussion_config?.reply_probability || 0) * 100)}%</div>
                          </>
                        ) : (
                          '-'
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">{chat.join_attempts}</td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-3">
                      {editing.chatId === chat.id ? (
                        <>
                          <button onClick={() => saveEdit(chat.id)} className="text-green-600 hover:underline">
                            Сохранить
                          </button>
                          <button onClick={cancelEdit} className="text-gray-600 hover:underline">
                            Отмена
                          </button>
                        </>
                      ) : (
                        <button onClick={() => startEdit(chat)} className="text-blue-600 hover:underline">
                          Настроить
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(chat.id)}
                        className="text-red-600 hover:underline"
                      >
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {jobs.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="font-medium mb-4">Импорты</h2>
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Файл</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Обработано</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Ошибок</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{job.file_name}</td>
                  <td className="px-4 py-3 text-sm">{job.status}</td>
                  <td className="px-4 py-3 text-sm">{job.processed_rows} / {job.total_rows}</td>
                  <td className="px-4 py-3 text-sm">{job.error_rows}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default CustomAutomationChatsPage;
