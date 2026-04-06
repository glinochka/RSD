/**
 * Agents Page
 * Display user's agents and manage full lifecycle
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import AgentsEmptyState from '../components/AgentsEmptyState';
import { useAsync } from '../hooks/useAsync';
import agentService from '../services/agentService';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import { useAuth } from '../context/useAuth';
import { validateFile } from '../utils/validation';
import '../styles/agentsPage.css';

const AGENTS_EMPTY_MESSAGE = 'У вас еще нет агентов, создайте прямо сейчас';
const AGENTS_EMPTY_CTA = 'Создайте прямо сейчас';
const fileIdentity = (file) => `${file.name}::${file.size}::${file.lastModified}`;
const linkIdentity = (link) => link.trim().toLowerCase();

const AgentCard = ({ agent, isSelected, onManage, onDelete, onToggle }) => {
  const agentName = agent.bot_username || agent.name || 'Агент';
  const isActive = !!agent.is_active;

  const handleSelect = () => {
    onManage(agent.bot_id);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onManage(agent.bot_id);
    }
  };

  return (
    <div
      className={`agent-item ${isSelected ? 'agent-item--selected' : ''}`}
      onClick={handleSelect}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`Выбрать агента ${agentName}`}
    >
      <div className="agent-info">
        <span
          className={`agent-status-dot ${isActive ? 'agent-status-dot--active' : 'agent-status-dot--inactive'}`}
          title={isActive ? 'Активен' : 'Не активен'}
        ></span>
        <div className="agent-details">
          <h3 className="agent-name">{agentName}</h3>
          <p className="agent-role">{isActive ? 'Активен' : 'Не активен'}</p>
        </div>
      </div>
      <div className="agent-actions">
        <button
          className="edit-btn"
          onClick={(event) => {
            event.stopPropagation();
            onManage(agent.bot_id);
          }}
          title="Управлять агентом"
          aria-label="Manage agent"
        >
          Управлять
        </button>
        <button
          className="edit-btn"
          onClick={(event) => {
            event.stopPropagation();
            onToggle(agent.bot_id);
          }}
          title={isActive ? 'Отключить агента' : 'Включить агента'}
          aria-label={isActive ? 'Disable agent' : 'Enable agent'}
        >
          {isActive ? 'OFF' : 'ON'}
        </button>
        <button
          className="delete-btn"
          onClick={(event) => {
            event.stopPropagation();
            onDelete(agent.bot_id);
          }}
          title="Delete agent"
          aria-label="Delete agent"
        >
          ×
        </button>
      </div>
    </div>
  );
};

const AgentsPageContent = () => {
  const navigate = useNavigate();
  const { showError, showSuccess } = useNotification();
  const { isAuthenticated } = useAuth();
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [isSavingWelcome, setIsSavingWelcome] = useState(false);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [isGeneratingWelcome, setIsGeneratingWelcome] = useState(false);
  const [isUploadingDocs, setIsUploadingDocs] = useState(false);
  const [isUploadingLink, setIsUploadingLink] = useState(false);
  const [pendingLink, setPendingLink] = useState('');
  const [systemPromptDraft, setSystemPromptDraft] = useState('');
  const [welcomeDraft, setWelcomeDraft] = useState('');
  const detailsRequestIdRef = useRef(0);
  const { data: agents, isLoading, execute } = useAsync(
    () => agentService.getAll(),
    false
  );

  useEffect(() => {
    if (!isAuthenticated) return;
    execute();
  }, [isAuthenticated]);

  const handleCreateAgent = () => {
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  };

  const handleOpenDetailedAnalytics = () => {
    if (!selectedBotId) {
      showError('Сначала выберите агента');
      return;
    }
    navigate(NAVIGATION_ROUTES.AGENT_ANALYTICS(selectedBotId));
  };

  const refreshAgents = async () => {
    const updated = await execute();
    return updated || [];
  };

  const loadAgentDetails = async (botId) => {
    const requestId = detailsRequestIdRef.current + 1;
    detailsRequestIdRef.current = requestId;
    setSelectedBotId(botId);
    setSelectedAgent(null);
    setDocuments([]);
    setIsLoadingDetails(true);
    try {
      const [agent, docs] = await Promise.all([
        agentService.getById(botId),
        agentService.getDocumentsByBotId(botId),
      ]);
      if (requestId !== detailsRequestIdRef.current) return;
      setSelectedAgent(agent);
      setSystemPromptDraft(agent.system_prompt || '');
      setWelcomeDraft(agent.welcome_message || '');
      setDocuments(docs || []);
    } catch (error) {
      if (requestId !== detailsRequestIdRef.current) return;
      showError(error?.message || 'Ошибка при загрузке карточки агента');
    } finally {
      if (requestId !== detailsRequestIdRef.current) return;
      setIsLoadingDetails(false);
    }
  };

  const handleDeleteAgent = async (botId) => {
    if (!window.confirm('Вы уверены, что хотите удалить агента?')) {
      return;
    }

    try {
      await agentService.delete(botId);
      showSuccess('Агент успешно удален!');
      const updatedAgents = await refreshAgents();
      if (selectedBotId === botId) {
        setSelectedBotId(null);
        setSelectedAgent(null);
        setDocuments([]);
        if (updatedAgents.length > 0) {
          await loadAgentDetails(updatedAgents[0].bot_id);
        }
      }
    } catch (error) {
      showError(error?.message || 'Ошибка при удалении агента');
    }
  };

  const handleToggleAgent = async (botId) => {
    try {
      const updatedAgent = await agentService.toggleStatus(botId);
      showSuccess('Статус агента обновлен');
      await refreshAgents();
      if (selectedBotId === botId) {
        setSelectedAgent((prev) => ({ ...(prev || {}), ...updatedAgent }));
      }
    } catch (error) {
      showError(error?.message || 'Ошибка при изменении статуса агента');
    }
  };

  const handleSaveSystemPrompt = async () => {
    if (!selectedBotId) return;
    if (!systemPromptDraft.trim()) {
      showError('Системный промпт не должен быть пустым');
      return;
    }

    setIsSavingPrompt(true);
    try {
      await agentService.update(selectedBotId, {
        system_prompt: systemPromptDraft.trim(),
      });
      showSuccess('Системный промпт обновлен');
      await loadAgentDetails(selectedBotId);
      await refreshAgents();
    } catch (error) {
      showError(error?.message || 'Ошибка при обновлении системного промпта');
    } finally {
      setIsSavingPrompt(false);
    }
  };

  const handleSaveWelcomeMessage = async () => {
    if (!selectedBotId) return;

    setIsSavingWelcome(true);
    try {
      await agentService.update(selectedBotId, {
        welcome_message: welcomeDraft.trim() || null,
      });
      showSuccess('Приветственное сообщение обновлено');
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при обновлении приветствия');
    } finally {
      setIsSavingWelcome(false);
    }
  };

  const handleAiImprovePrompt = async () => {
    if (!selectedBotId) return;
    setIsGeneratingPrompt(true);
    try {
      const result = await agentService.aiImprovePrompt(selectedBotId);
      const nextPrompt = result?.system_prompt || '';
      setSystemPromptDraft(nextPrompt);
      setSelectedAgent((prev) => ({ ...(prev || {}), system_prompt: nextPrompt }));
      showSuccess('ИИ улучшил системный промпт');
      await refreshAgents();
    } catch (error) {
      showError(error?.message || 'Ошибка при улучшении промпта через ИИ');
    } finally {
      setIsGeneratingPrompt(false);
    }
  };

  const handleAiGenerateWelcome = async () => {
    if (!selectedBotId) return;
    setIsGeneratingWelcome(true);
    try {
      const result = await agentService.aiGenerateWelcome(selectedBotId);
      const nextWelcome = result?.welcome_message || '';
      setWelcomeDraft(nextWelcome);
      setSelectedAgent((prev) => ({ ...(prev || {}), welcome_message: nextWelcome }));
      showSuccess('ИИ сгенерировал приветствие');
    } catch (error) {
      showError(error?.message || 'Ошибка при генерации приветствия через ИИ');
    } finally {
      setIsGeneratingWelcome(false);
    }
  };

  const handleUploadDocuments = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!selectedBotId || files.length === 0) return;
    const uniqueFiles = Array.from(new Map(files.map((f) => [fileIdentity(f), f])).values());

    const validFiles = [];
    const fileErrors = [];
    uniqueFiles.forEach((file) => {
      const check = validateFile(file);
      if (check.isValid) {
        validFiles.push(file);
      } else {
        fileErrors.push(`${file.name}: ${check.errors.join(', ')}`);
      }
    });

    if (fileErrors.length > 0) {
      showError(`Ошибки файлов:\n${fileErrors.join('\n')}`);
    }
    if (validFiles.length === 0) {
      event.target.value = '';
      return;
    }

    setIsUploadingDocs(true);
    try {
      for (const file of validFiles) {
        const res = await agentService.uploadDocumentByBotId(selectedBotId, file);
        if (res?.status === 'limit_error') {
          showError(
            `Лимит базы знаний превышен: план ${res.current_plan}, лимит ${res.limit}, уже ${res.current_count}, файл добавит ${res.new_chunks_count}`
          );
          break;
        }
        if (res?.status === 'duplicate') {
          showSuccess(`Файл ${file.name} уже загружен ранее (статус: ${res?.document_status || 'ready'})`);
          continue;
        }
        if (res?.status === 'reprocessing') {
          showSuccess(`Файл ${file.name} отправлен на повторную обработку`);
          continue;
        }
        showSuccess(`Файл ${file.name} принят к обработке`);
      }
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при загрузке документов');
    } finally {
      setIsUploadingDocs(false);
      event.target.value = '';
    }
  };

  const isValidPublicUrl = (value) => {
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const handleUploadLink = async () => {
    const normalized = pendingLink.trim();
    if (!selectedBotId) {
      return;
    }
    if (!normalized) {
      showError('Введите ссылку для добавления');
      return;
    }
    if (!isValidPublicUrl(normalized)) {
      showError('Некорректная ссылка. Разрешены только публичные http/https URL');
      return;
    }

    setIsUploadingLink(true);
    try {
      const res = await agentService.uploadPublicLinkByBotId(selectedBotId, normalized);
      if (res?.status === 'limit_error') {
        showError(
          `Лимит базы знаний превышен: план ${res.current_plan}, лимит ${res.limit}, уже ${res.current_count}, ссылка добавит ${res.new_chunks_count}`
        );
        return;
      }
      if (res?.status === 'duplicate') {
        showSuccess(`Ссылка уже добавлена ранее (статус: ${res?.document_status || 'ready'})`);
        return;
      }
      showSuccess('Ссылка принята к обработке');
      setPendingLink('');
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при добавлении ссылки');
    } finally {
      setIsUploadingLink(false);
    }
  };

  const handleLinkKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleUploadLink();
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (!window.confirm('Удалить документ из базы знаний агента?')) {
      return;
    }
    try {
      await agentService.deleteDocumentById(docId);
      showSuccess('Документ удален');
      if (selectedBotId) {
        await loadAgentDetails(selectedBotId);
      }
    } catch (error) {
      showError(error?.message || 'Ошибка при удалении документа');
    }
  };

  const handleCopyApiKey = async () => {
    const key = selectedAgent?.external_api_key;
    if (!key) {
      showError('API ключ не найден');
      return;
    }

    try {
      await navigator.clipboard.writeText(key);
      showSuccess('API ключ скопирован');
    } catch (error) {
      showError('Не удалось скопировать API ключ');
    }
  };

  const handleRegenerateApiKey = async () => {
    if (!selectedBotId) return;
    if (!window.confirm('Вы точно хотите перевыпустить ключ? Нынешний ключ больше не будет активен.')) {
      return;
    }
    try {
      const updated = await agentService.regenerateExternalKey(selectedBotId);
      setSelectedAgent((prev) => ({ ...(prev || {}), ...updated }));
      showSuccess('API ключ перевыпущен');
    } catch (error) {
      showError(error?.message || 'Ошибка перевыпуска API ключа');
    }
  };

  useEffect(() => {
    if (!isAuthenticated) return;
    const list = agents || [];
    if (list.length > 0 && !selectedBotId) {
      loadAgentDetails(list[0].bot_id);
    }
  }, [agents, isAuthenticated, selectedBotId]);

  const selectedAgentName = useMemo(() => {
    if (!selectedAgent) return '';
    return selectedAgent.bot_username ? `@${selectedAgent.bot_username}` : `Агент #${selectedAgent.bot_id}`;
  }, [selectedAgent]);

  if (isLoading && isAuthenticated) {
    return <Loading message="Загрузка агентов..." />;
  }

  const displayAgents = agents || [];
  const showEmptyAgentsList = !isAuthenticated || displayAgents.length === 0;

  return (
    <div className="agents-page-content">
      <section className="agents-section">
        <div className="section-header">
          <h2 className="section-title">Ваши агенты:</h2>
          <button type="button" className="btn btn-black btn-add" onClick={handleCreateAgent}>
            + Новый агент
          </button>
        </div>

        {showEmptyAgentsList ? (
          <AgentsEmptyState
            message={AGENTS_EMPTY_MESSAGE}
            ctaLabel={AGENTS_EMPTY_CTA}
            onCtaClick={handleCreateAgent}
          />
        ) : (
          <div className="agents-layout">
            <div className="agents-list">
              {displayAgents.map((agent) => (
                <AgentCard
                  key={agent.bot_id}
                  agent={agent}
                  isSelected={selectedBotId === agent.bot_id}
                  onManage={loadAgentDetails}
                  onDelete={handleDeleteAgent}
                  onToggle={handleToggleAgent}
                />
              ))}
            </div>

            <div className="agent-management-card">
              {!selectedAgent || isLoadingDetails ? (
                <div className="agent-management-empty">
                  {isLoadingDetails ? 'Загрузка карточки агента...' : 'Выберите агента для управления'}
                </div>
              ) : (
                <>
                  <div className="agent-management-header">
                    <h3>{selectedAgentName}</h3>
                    <p>ID: {selectedAgent.bot_id}</p>
                    <button
                      type="button"
                      className="btn btn-black analytics-btn"
                      onClick={handleOpenDetailedAnalytics}
                    >
                      Детальная аналитика
                    </button>
                  </div>

                  <div className="agent-management-block">
                    <label>API ключ для внешних интеграций</label>
                    <div className="api-key-row">
                      <button
                        className="btn btn-black"
                        onClick={handleCopyApiKey}
                        title="Скопировать API ключ"
                        aria-label="Copy API key"
                      >
                        Скопировать API ключ
                      </button>
                      <button
                        className="btn btn-outline"
                        onClick={handleRegenerateApiKey}
                        title="Перевыпустить API ключ"
                        aria-label="Regenerate API key"
                      >
                        Перевыпустить API ключ
                      </button>
                    </div>
                  </div>

                  <div className="agent-management-block">
                    <label htmlFor="system_prompt">Системный промпт</label>
                    <textarea
                      id="system_prompt"
                      rows="6"
                      className="input-main textarea"
                      value={systemPromptDraft}
                      onChange={(e) => setSystemPromptDraft(e.target.value)}
                    />
                    <button
                      className="btn btn-black"
                      onClick={handleSaveSystemPrompt}
                      disabled={isSavingPrompt}
                    >
                      {isSavingPrompt ? 'Сохранение...' : 'Сохранить промпт'}
                    </button>
                    <button
                      className="btn btn-black"
                      onClick={handleAiImprovePrompt}
                      disabled={isGeneratingPrompt}
                    >
                      {isGeneratingPrompt ? 'ИИ улучшает...' : 'Улучшить промпт ИИ'}
                    </button>
                  </div>

                  <div className="agent-management-block">
                    <label htmlFor="welcome_message">Приветственное сообщение (/start)</label>
                    <textarea
                      id="welcome_message"
                      rows="3"
                      className="input-main textarea"
                      value={welcomeDraft}
                      onChange={(e) => setWelcomeDraft(e.target.value)}
                      placeholder="Введите приветствие или оставьте пустым"
                    />
                    <button
                      className="btn btn-black"
                      onClick={handleSaveWelcomeMessage}
                      disabled={isSavingWelcome}
                    >
                      {isSavingWelcome ? 'Сохранение...' : 'Сохранить приветствие'}
                    </button>
                    <button
                      className="btn btn-black"
                      onClick={handleAiGenerateWelcome}
                      disabled={isGeneratingWelcome}
                    >
                      {isGeneratingWelcome ? 'ИИ генерирует...' : 'Сгенерировать приветствие ИИ'}
                    </button>
                  </div>

                  <div className="agent-management-block">
                    <div className="docs-header-row">
                      <label>База знаний (документы и ссылки)</label>
                      <label className="btn btn-black docs-upload-btn">
                        {isUploadingDocs ? 'Загрузка...' : '+ Добавить файлы'}
                        <input
                          type="file"
                          multiple
                          accept=".pdf,.doc,.docx,.txt"
                          onChange={handleUploadDocuments}
                          disabled={isUploadingDocs}
                          hidden
                        />
                      </label>
                    </div>
                    <div className="kb-link-row">
                      <input
                        type="url"
                        className="input-main"
                        value={pendingLink}
                        onChange={(e) => setPendingLink(e.target.value)}
                        onKeyDown={handleLinkKeyDown}
                        placeholder="https://example.com/article"
                        disabled={isUploadingLink}
                      />
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={handleUploadLink}
                        disabled={isUploadingLink}
                      >
                        {isUploadingLink ? 'Добавление...' : '+ Добавить ссылку'}
                      </button>
                    </div>
                    <p className="docs-empty">Ссылка обрабатывается один раз и не обновляется автоматически</p>
                    {documents.length === 0 ? (
                      <p className="docs-empty">Документы не добавлены</p>
                    ) : (
                      <div className="docs-list-web">
                        {documents.map((doc) => (
                          <div key={`${doc.id}-${linkIdentity(doc.file_name || '')}`} className="doc-row">
                            <div className="doc-meta">
                              <span className="doc-name">{doc.file_name}</span>
                              <span className={`doc-status doc-status--${doc.status}`}>{doc.status}</span>
                            </div>
                            <button
                              className="delete-btn"
                              onClick={() => handleDeleteDocument(doc.id)}
                              aria-label="Delete document"
                              title="Удалить документ"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

const AgentsPage = () => {
  return (
    <MainLayout>
      <AgentsPageContent />
    </MainLayout>
  );
};

export default AgentsPage;