import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

const PROMPT_TYPE_LABELS = {
  chat_monitoring_trigger: 'Мониторинг: триггер',
  chat_monitoring_response: 'Мониторинг: ответ',
  neurocommenting: 'Нейрокомментинг',
  discussion_reply: 'Обсуждения',
  dmp_outreach: 'DMP прогрев',
  lead_qualification: 'Квалификация лида',
  chat_relevance: 'Релевантность чата',
  profile_bio: 'Профиль bio',
};

const VARIABLE_HINTS = {
  chat_monitoring_trigger: ['text'],
  chat_monitoring_response: ['text'],
  neurocommenting: ['post_text', 'chat_title'],
  discussion_reply: ['message_text', 'chat_title'],
  dmp_outreach: ['name', 'company'],
  lead_qualification: ['history', 'last_incoming'],
  chat_relevance: ['query', 'title', 'description', 'chat_type', 'participants_count'],
  profile_bio: ['industry', 'name'],
};

const CustomAutomationPromptsPage = () => {
  const { id } = useParams();
  const [prompts, setPrompts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const loadPrompts = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await customService.getPrompts(id);
      setPrompts(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load prompts');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadPrompts();
  }, [loadPrompts]);

  const handleToggle = async (promptId) => {
    setMessage(null);
    try {
      await customService.togglePrompt(id, promptId);
      setMessage('Статус промпта обновлён');
      await loadPrompts();
    } catch (err) {
      setError(err.message || 'Failed to toggle prompt');
    }
  };

  const grouped = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.prompt_type]) {
      acc[prompt.prompt_type] = [];
    }
    acc[prompt.prompt_type].push(prompt);
    return acc;
  }, {});

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Промпты</h1>
        <Link
          to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id)}
          className="text-sm text-blue-600 hover:underline"
        >
          Настройки модулей
        </Link>
      </div>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      {isLoading ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="text-gray-500 text-center py-6">Промптов пока нет. Создайте автоматизацию заново — шаблоны появятся автоматически.</div>
      ) : (
        Object.entries(grouped).map(([type, items]) => (
          <div key={type} className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-medium">{PROMPT_TYPE_LABELS[type] || type}</h2>
              <div className="text-xs text-gray-500">
                Переменные: {VARIABLE_HINTS[type]?.map((v) => `{${v}}`).join(', ') || '-'}
              </div>
            </div>
            <div className="space-y-3">
              {items.map((prompt) => (
                <div
                  key={prompt.id}
                  className={`border rounded p-3 flex items-start justify-between ${prompt.is_active ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-gray-50'}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium">{prompt.name}</span>
                      <span className="text-xs text-gray-500">v{prompt.version}</span>
                      {prompt.is_active ? (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Активен</span>
                      ) : (
                        <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded">Архив</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 mb-1">
                      {prompt.model} • temp {prompt.temperature} • max_tokens {prompt.max_tokens}
                    </div>
                    <div className="text-sm text-gray-700 line-clamp-3 whitespace-pre-wrap">{prompt.content}</div>
                  </div>
                  <div className="flex flex-col gap-2 ml-4">
                    <Link
                      to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPT_EDIT(id, prompt.id)}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      Редактировать
                    </Link>
                    <button
                      onClick={() => handleToggle(prompt.id)}
                      className="text-sm text-gray-600 hover:underline text-left"
                    >
                      {prompt.is_active ? 'Отключить' : 'Включить'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
};

export default CustomAutomationPromptsPage;
