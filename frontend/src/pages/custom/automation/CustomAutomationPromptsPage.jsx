import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { PROMPT_TYPE_LABELS, VARIABLE_HINTS } from './activityLabels';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

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
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Промпты</h1>
          <p className="crm-subtitle">Шаблоны ответов по модулям автоматизации.</p>
        </div>
        <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id)} className="btn btn-outline">
          Настройки модулей
        </Link>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      {isLoading ? (
        <div className="crm-empty-list"><p>Загрузка...</p></div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="crm-empty-list">
          <p>Промптов пока нет</p>
          <span>Создайте автоматизацию заново — шаблоны появятся автоматически.</span>
        </div>
      ) : (
        Object.entries(grouped).map(([type, items]) => (
          <div key={type} className="settings-section">
            <h3 className="settings-section-title">{PROMPT_TYPE_LABELS[type] || type}</h3>
            <p className="form-hint">
              Переменные: {VARIABLE_HINTS[type]?.map((v) => `{${v}}`).join(', ') || '-'}
            </p>
            <div className="crm-list">
              {items.map((prompt) => (
                <div key={prompt.id} className="crm-item">
                  <div className="crm-item-header">
                    <h5 className="crm-item-title">{prompt.name}</h5>
                    <span className={`crm-status ${prompt.is_active ? 'crm-status--confirmed' : 'crm-status--completed'}`}>
                      {prompt.is_active ? 'Активен' : 'Архив'}
                    </span>
                  </div>
                  <p className="crm-item-subtitle">
                    v{prompt.version} · {prompt.model} · temp {prompt.temperature} · max_tokens {prompt.max_tokens}
                  </p>
                  <p className="crm-prompt-preview">{prompt.content}</p>
                  <div className="crm-item-actions">
                    <Link
                      to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPT_EDIT(id, prompt.id)}
                      className="btn btn-black"
                    >
                      Редактировать
                    </Link>
                    <button type="button" onClick={() => handleToggle(prompt.id)} className="btn btn-outline">
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
