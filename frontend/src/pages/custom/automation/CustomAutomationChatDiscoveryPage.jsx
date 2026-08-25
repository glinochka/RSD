import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { CHAT_MODE_OPTIONS_WITHOUT_INACTIVE } from './activityLabels';

const MODES = CHAT_MODE_OPTIONS_WITHOUT_INACTIVE;

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
    require_approval: false,
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
    <>
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}
      {message ? <p className="crm-flash">{message}</p> : null}

      <form onSubmit={handleSubmit} className="settings-section">
        <h3 className="settings-section-title">Автопоиск</h3>
        <div className="form-group">
          <label htmlFor="discovery-query">Тема / запрос</label>
          <input
            id="discovery-query"
            type="text"
            value={form.query}
            onChange={(e) => setForm((prev) => ({ ...prev, query: e.target.value }))}
            placeholder="SEO оптимизация"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="discovery-mode">Режим чатов</label>
          <CustomSelect
            id="discovery-mode"
            value={form.mode}
            options={MODES}
            onChange={(e) => setForm((prev) => ({ ...prev, mode: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="discovery-max">Макс. чатов</label>
          <input
            id="discovery-max"
            type="number"
            value={form.max_chats}
            min={1}
            max={200}
            onChange={(e) => setForm((prev) => ({ ...prev, max_chats: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="discovery-threshold">Порог релевантности</label>
          <input
            id="discovery-threshold"
            type="number"
            step={0.05}
            min={0}
            max={1}
            value={form.relevance_threshold}
            onChange={(e) => setForm((prev) => ({ ...prev, relevance_threshold: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <FeatureToggle
            title="Ручное одобрение"
            checked={form.require_approval}
            onChange={(checked) => setForm((prev) => ({ ...prev, require_approval: checked }))}
          />
        </div>
        <div className="settings-actions">
          <button type="submit" disabled={isStarting} className="btn btn-black">
            {isStarting ? 'Запуск...' : 'Найти чаты'}
          </button>
        </div>
      </form>

      {isLoading ? (
        <div className="crm-empty-list"><p>Загрузка...</p></div>
      ) : tasks.length === 0 ? (
        <div className="crm-empty-list">
          <p>Задач поиска пока нет</p>
          <span>Укажите тему — система найдёт чаты сама.</span>
        </div>
      ) : (
        <div className="crm-list">
          {tasks.map((task) => (
            <div key={task.id} className="crm-item">
              <div className="crm-item-header">
                <h5 className="crm-item-title">Задача #{task.id}</h5>
                <span className="crm-status">{task.status}</span>
              </div>
              <p className="crm-item-subtitle">Запрос: {task.query}</p>
              <p className="crm-item-subtitle">
                Найдено: {(task.found_chats || []).length} / Одобрено: {task.joined_chats} / Отклонено: {task.rejected_chats}
              </p>
              {task.status === 'awaiting_approval' ? (
                <>
                  {(task.found_chats || []).map((chat, idx) => (
                    <div key={chat.id || idx} className="form-group">
                      <FeatureToggle
                        title={chat.title || chat.username || 'Без названия'}
                        checked={selected[task.id]?.includes(idx) || false}
                        onChange={() => toggleSelected(task.id, idx)}
                      />
                      <span className="form-hint">
                        {chat.chat_type} · {chat.participants_count || 0} участников · релевантность {Math.round((chat.score || 0) * 100)}%
                        {chat.reason ? ` · ${chat.reason}` : ''}
                      </span>
                    </div>
                  ))}
                  <div className="crm-item-actions">
                    <button type="button" onClick={() => handleApprove(task.id)} className="btn btn-black">
                      Одобрить выбранные
                    </button>
                    <button type="button" onClick={() => handleReject(task.id)} className="btn btn-outline">
                      Отклонить выбранные
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </>
  );
};

export default CustomAutomationChatDiscoveryPage;
