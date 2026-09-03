import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { parseShillingContent, PROMPT_TYPE_LABELS, VARIABLE_HINTS } from './activityLabels';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

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
      const pair = data.prompt_type === 'shilling'
        ? parseShillingContent(data.content)
        : { setup: '', reply: '' };
      setForm({
        content: data.content,
        model: data.model,
        temperature: data.temperature,
        max_tokens: data.max_tokens,
        shilling_setup: data.shilling_setup || pair.setup,
        shilling_reply: data.shilling_reply || pair.reply,
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
      const payload = prompt.prompt_type === 'shilling'
        ? {
            shilling_setup: form.shilling_setup || '',
            shilling_reply: form.shilling_reply || '',
          }
        : {
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
    return (
      <div className="project-settings-page project-settings-page--loading">
        <div className="settings-loading">
          <div className="spinner" />
          <p>Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!prompt) {
    return (
      <div className="project-settings-page">
        <p className="form-hint">{error || 'Промпт не найден'}</p>
      </div>
    );
  }

  const variables = VARIABLE_HINTS[prompt.prompt_type] || [];

  return (
    <div className="project-settings-page">
      <div className="settings-header">
        <div>
          <h1 className="settings-title">Редактирование промпта</h1>
          <p className="settings-subtitle">
            {PROMPT_TYPE_LABELS[prompt.prompt_type] || prompt.prompt_type} · v{prompt.version}
          </p>
        </div>
        <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)} className="btn btn-outline">
          К списку
        </Link>
      </div>

      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}

      <form onSubmit={handleSubmit} className="settings-form">
        <div className="settings-section">
          <h3 className="settings-section-title">Параметры</h3>
          {prompt.prompt_type === 'shilling' ? (
            <>
              <p className="form-hint">Фиксированные фразы. Первый аккаунт пишет вопрос, второй — ответ.</p>
              <div className="form-group">
                <label htmlFor="shilling_setup">1. Сообщение (вопрос)</label>
                <textarea
                  id="shilling_setup"
                  name="shilling_setup"
                  value={form.shilling_setup || ''}
                  onChange={handleChange}
                  rows={4}
                />
              </div>
              <div className="form-group">
                <label htmlFor="shilling_reply">2. Сообщение (ответ)</label>
                <textarea
                  id="shilling_reply"
                  name="shilling_reply"
                  value={form.shilling_reply || ''}
                  onChange={handleChange}
                  rows={4}
                />
              </div>
            </>
          ) : (
            <>
          <div className="form-group">
            <label htmlFor="model">Модель</label>
            <input id="model" type="text" name="model" value={form.model} onChange={handleChange} />
          </div>
          <div className="form-group">
            <label htmlFor="temperature">Temperature</label>
            <input
              id="temperature"
              type="number"
              step="0.1"
              min="0"
              max="2"
              name="temperature"
              value={form.temperature}
              onChange={handleChange}
            />
          </div>
          <div className="form-group">
            <label htmlFor="max_tokens">Max tokens</label>
            <input id="max_tokens" type="number" name="max_tokens" value={form.max_tokens} onChange={handleChange} />
          </div>
          <div className="form-group">
            <label htmlFor="content">Содержимое промпта</label>
            <span className="form-hint">Переменные: {variables.map((v) => `{${v}}`).join(', ')}</span>
            <textarea id="content" name="content" value={form.content} onChange={handleChange} rows={12} />
          </div>
            </>
          )}
          <div className="settings-actions">
            <button type="submit" disabled={isSaving} className="btn btn-black">
              {isSaving ? 'Сохранение...' : 'Сохранить новую версию'}
            </button>
          </div>
        </div>
      </form>

      {prompt.prompt_type === 'shilling' ? null : (
      <div className="settings-section">
        <h3 className="settings-section-title">Тестирование</h3>
        {variables.map((v) => (
          <div key={v} className="form-group">
            <label htmlFor={`var-${v}`}>{`{${v}}`}</label>
            <input
              id={`var-${v}`}
              type="text"
              value={testVariables[v] || ''}
              onChange={(e) => handleVariableChange(v, e.target.value)}
            />
          </div>
        ))}
        <div className="settings-actions">
          <button type="button" onClick={handleTest} disabled={isTesting} className="btn btn-outline">
            {isTesting ? 'Тестирование...' : 'Тестировать'}
          </button>
        </div>
        {testResult ? (
          <>
            {testResult.missing_variables?.length > 0 ? (
              <p className="form-hint">
                Не заполнены переменные: {testResult.missing_variables.map((v) => `{${v}}`).join(', ')}
              </p>
            ) : null}
            <div className="form-group">
              <label>Собранный промпт</label>
              <p className="crm-prompt-preview">{testResult.rendered}</p>
            </div>
            <div className="form-group">
              <label>Результат LLM</label>
              <p className="crm-prompt-preview">{testResult.error || testResult.output}</p>
            </div>
          </>
        ) : null}
      </div>
      )}
    </div>
  );
};

export default CustomAutomationPromptEditPage;
