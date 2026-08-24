import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';

const MODES = [
  { value: 'monitoring', label: 'Мониторинг' },
  { value: 'neurocommenting', label: 'Нейрокомментинг' },
  { value: 'discussion', label: 'Обсуждения' },
];

const CustomAutomationChatDiscoveryPage = () => {
  const { id } = useParams();
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [form, setForm] = useState({
    query: '',
    mode: 'monitoring',
    max_chats: 30,
    require_approval: true,
    relevance_threshold: 0.6,
  });
  const [selected, setSelected] = useState({});

  const loadTasks = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getDiscoveryTasks(id, { limit: 50 });
      setTasks(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load discovery tasks');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    const hasInFlight = tasks.some((task) => task.status === 'pending' || task.status === 'processing');
    if (!hasInFlight) {
      return undefined;
    }
    const timer = setInterval(() => {
      loadTasks();
    }, 8000);
    return () => clearInterval(timer);
  }, [tasks, loadTasks]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsStarting(true);
    setMessage(null);
    setError(null);
    try {
      await customService.createDiscoveryTask(id, {
        query: form.query,
        mode: form.mode,
        max_chats: Number(form.max_chats),
        require_approval: form.require_approval,
        relevance_threshold: Number(form.relevance_threshold),
      });
      setMessage('Поиск чатов запущен в фоне. Обновите страницу через минуту.');
      setForm((prev) => ({ ...prev, query: '' }));
      await loadTasks();
    } catch (err) {
      setError(err.message || 'Failed to start discovery');
    } finally {
      setIsStarting(false);
    }
  };

  const toggleSelected = (taskId, idx) => {
    setSelected((prev) => {
      const key = `${taskId}`;
      const set = new Set(prev[key] || []);
      if (set.has(idx)) {
        set.delete(idx);
      } else {
        set.add(idx);
      }
      return { ...prev, [key]: Array.from(set) };
    });
  };

  const handleApprove = async (taskId) => {
    setMessage(null);
    setError(null);
    try {
      const indices = selected[taskId] || [];
      await customService.approveDiscoveryTask(id, taskId, indices);
      setMessage(`Одобрено чатов: ${indices.length}`);
      await loadTasks();
    } catch (err) {
      setError(err.message || 'Failed to approve chats');
    }
  };

  const handleReject = async (taskId) => {
    setMessage(null);
    setError(null);
    try {
      const indices = selected[taskId] || [];
      await customService.rejectDiscoveryTask(id, taskId, indices);
      setMessage(`Отклонено чатов: ${indices.length}`);
      await loadTasks();
    } catch (err) {
      setError(err.message || 'Failed to reject chats');
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Автопоиск чатов и каналов</h1>
      {error && <div className="text-red-600">{error}</div>}
      {message && <div className="text-green-600">{message}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Тема / запрос</label>
          <input
            type="text"
            value={form.query}
            onChange={(e) => setForm((prev) => ({ ...prev, query: e.target.value }))}
            placeholder="SEO оптимизация"
            className="w-full border border-gray-300 rounded px-3 py-2"
            required
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Режим чатов</label>
            <select
              value={form.mode}
              onChange={(e) => setForm((prev) => ({ ...prev, mode: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Макс. чатов</label>
            <input
              type="number"
              value={form.max_chats}
              min={1}
              max={200}
              onChange={(e) => setForm((prev) => ({ ...prev, max_chats: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Порог релевантности</label>
            <input
              type="number"
              step={0.05}
              min={0}
              max={1}
              value={form.relevance_threshold}
              onChange={(e) => setForm((prev) => ({ ...prev, relevance_threshold: e.target.value }))}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="require_approval"
            type="checkbox"
            checked={form.require_approval}
            onChange={(e) => setForm((prev) => ({ ...prev, require_approval: e.target.checked }))}
          />
          <label htmlFor="require_approval" className="text-sm text-gray-700">
            Требовать ручного одобрения перед вступлением
          </label>
        </div>
        <button
          type="submit"
          disabled={isStarting}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isStarting ? 'Запуск...' : 'Найти чаты'}
        </button>
      </form>

      {isLoading ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : tasks.length === 0 ? (
        <div className="text-gray-500 text-center py-6">Задач поиска пока нет.</div>
      ) : (
        <div className="space-y-4">
          {tasks.map((task) => (
            <div key={task.id} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium">Задача #{task.id}</div>
                <div className="text-sm text-gray-500">{task.status}</div>
              </div>
              <div className="text-sm text-gray-700 mb-2">Запрос: {task.query}</div>
              <div className="text-sm text-gray-500 mb-2">
                Найдено: {task.found_chats.length} / Одобрено: {task.joined_chats} / Отклонено: {task.rejected_chats}
              </div>
              {task.status === 'awaiting_approval' && (
                <div className="mt-3 space-y-2">
                  {task.found_chats.map((chat, idx) => (
                    <div
                      key={chat.id || idx}
                      className="flex items-start gap-3 p-2 border rounded hover:bg-gray-50"
                    >
                      <input
                        type="checkbox"
                        checked={selected[task.id]?.includes(idx) || false}
                        onChange={() => toggleSelected(task.id, idx)}
                      />
                      <div className="flex-1">
                        <div className="font-medium">{chat.title || chat.username || 'Без названия'}</div>
                        <div className="text-sm text-gray-600">{chat.description}</div>
                        <div className="text-xs text-gray-500 mt-1">
                          {chat.chat_type} · {chat.participants_count || 0} участников · релевантность {Math.round((chat.score || 0) * 100)}%
                        </div>
                        {chat.reason && (
                          <div className="text-xs text-gray-500 mt-1">{chat.reason}</div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={() => handleApprove(task.id)}
                      className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700"
                    >
                      Одобрить выбранные
                    </button>
                    <button
                      onClick={() => handleReject(task.id)}
                      className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700"
                    >
                      Отклонить выбранные
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CustomAutomationChatDiscoveryPage;
