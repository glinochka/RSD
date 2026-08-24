import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';

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

const CustomAutomationPromptEditPage = () => {
  const { id, promptId } = useParams();
  const [prompt, setPrompt] = useState(null);
  const [form, setForm] = useState({});
  const [testVariables, setTestVariables] = useState({});
  const [testResult, setTestResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const loadPrompt = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await customService.getPrompt(id, promptId);
      setPrompt(data);
      setForm({
        content: data.content,
        model: data.model,
        temperature: data.temperature,
        max_tokens: data.max_tokens,
      });
      const vars = VARIABLE_HINTS[data.prompt_type] || [];
      const initial = {};
      vars.forEach((v) => {
        initial[v] = '';
      });
      setTestVariables(initial);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load prompt');
    } finally {
      setIsLoading(false);
    }
  }, [id, promptId]);

  useEffect(() => {
    loadPrompt();
  }, [loadPrompt]);

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'number' ? (value === '' ? '' : Number(value)) : value,
    }));
  };

  const handleVariableChange = (key, value) => {
    setTestVariables((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      const payload = {
        content: form.content,
        model: form.model,
        temperature: Number(form.temperature),
        max_tokens: Number(form.max_tokens),
      };
      await customService.updatePrompt(id, promptId, payload);
      setMessage('Промпт сохранён. Создана новая версия.');
      await loadPrompt();
    } catch (err) {
      setError(err.message || 'Failed to save prompt');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const result = await customService.testPrompt(id, promptId, testVariables);
      setTestResult(result);
    } catch (err) {
      setError(err.message || 'Test failed');
    } finally {
      setIsTesting(false);
    }
  };

  if (isLoading) {
    return <div className="text-gray-500">Загрузка...</div>;
  }

  if (!prompt) {
    return <div className="text-red-600">{error || 'Промпт не найден'}</div>;
  }

  const variables = VARIABLE_HINTS[prompt.prompt_type] || [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Редактирование промпта</h1>
          <div className="text-sm text-gray-500">
            {PROMPT_TYPE_LABELS[prompt.prompt_type] || prompt.prompt_type} • v{prompt.version}
          </div>
        </div>
        <Link
          to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)}
          className="text-sm text-blue-600 hover:underline"
        >
          ← К списку промптов
        </Link>
      </div>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Модель</label>
            <input
              type="text"
              name="model"
              value={form.model}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              name="temperature"
              value={form.temperature}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max tokens</label>
            <input
              type="number"
              name="max_tokens"
              value={form.max_tokens}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium text-gray-700">Содержимое промпта</label>
            <div className="text-xs text-gray-500">
              Переменные: {variables.map((v) => `{${v}}`).join(', ')}
            </div>
          </div>
          <textarea
            name="content"
            value={form.content}
            onChange={handleChange}
            rows={12}
            className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm"
          />
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={isSaving}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? 'Сохранение...' : 'Сохранить новую версию'}
          </button>
        </div>
      </form>

      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="font-medium">Тестирование</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {variables.map((v) => (
            <div key={v}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{`{${v}}`}</label>
              <input
                type="text"
                value={testVariables[v] || ''}
                onChange={(e) => handleVariableChange(v, e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2"
              />
            </div>
          ))}
        </div>
        <button
          onClick={handleTest}
          disabled={isTesting}
          className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
        >
          {isTesting ? 'Тестирование...' : 'Тестировать'}
        </button>

        {testResult && (
          <div className="space-y-4">
            {testResult.missing_variables?.length > 0 && (
              <div className="text-orange-600 text-sm">
                Не заполнены переменные: {testResult.missing_variables.map((v) => `{${v}}`).join(', ')}
              </div>
            )}
            <div>
              <div className="text-sm font-medium text-gray-700 mb-1">Сrendered:</div>
              <div className="bg-gray-50 rounded p-3 text-sm whitespace-pre-wrap font-mono">{testResult.rendered}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-700 mb-1">Результат LLM:</div>
              <div className="bg-gray-50 rounded p-3 text-sm whitespace-pre-wrap font-mono">
                {testResult.error ? (
                  <span className="text-red-600">{testResult.error}</span>
                ) : (
                  testResult.output
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationPromptEditPage;
