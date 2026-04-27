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
const isPortraitFeatureEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_chat_portrait !== false;
};
const channelLabel = (channel) => {
  if (!channel) return 'Канал';
  if (channel.provider === 'telegram_bot') return 'Telegram бот';
  if (channel.provider === 'telegram_userbot') return 'Telegram userbot';
  if (channel.provider === 'whatsapp_userbot') return 'WhatsApp userbot';
  if (channel.provider === 'whatsapp_business_api') return 'WhatsApp Business API';
  return channel.provider || 'Канал';
};
const WIDGET_TEMPLATE_TYPES = new Set(['qa', 'crm_admin']);

const AgentCard = ({ agent, isSelected, onManage, onDelete, onToggle }) => {
  const agentName = agent.bot_username || agent.name || 'Агент';
  const isActive = !!agent.is_active;

  const handleSelect = () => {
    onManage(agent.id);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onManage(agent.id);
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
            onManage(agent.id);
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
            onToggle(agent.id);
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
            onDelete(agent.id);
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
  const [isSavingPortraitFeature, setIsSavingPortraitFeature] = useState(false);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [isGeneratingWelcome, setIsGeneratingWelcome] = useState(false);
  const [isUploadingDocs, setIsUploadingDocs] = useState(false);
  const [isUploadingLink, setIsUploadingLink] = useState(false);
  const [pendingLink, setPendingLink] = useState('');
  const [systemPromptDraft, setSystemPromptDraft] = useState('');
  const [welcomeDraft, setWelcomeDraft] = useState('');
  const [channels, setChannels] = useState([]);
  const [isChannelsModalOpen, setIsChannelsModalOpen] = useState(false);
  const [channelModalTab, setChannelModalTab] = useState('bot');
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);
  const [isSavingChannel, setIsSavingChannel] = useState(false);
  const [botTokenDraft, setBotTokenDraft] = useState('');
  const [makePrimaryChannel, setMakePrimaryChannel] = useState(false);
  const [userbotApiId, setUserbotApiId] = useState('');
  const [userbotApiHash, setUserbotApiHash] = useState('');
  const [userbotPhone, setUserbotPhone] = useState('');
  const [userbotCode, setUserbotCode] = useState('');
  const [userbotPassword, setUserbotPassword] = useState('');
  const [userbotAuthToken, setUserbotAuthToken] = useState('');
  const [userbotSessionString, setUserbotSessionString] = useState('');
  const [isSendingUserbotCode, setIsSendingUserbotCode] = useState(false);
  const [isVerifyingUserbotCode, setIsVerifyingUserbotCode] = useState(false);
  const [whatsappUserbotPhone, setWhatsappUserbotPhone] = useState('');
  const [whatsappUserbotSessionString, setWhatsappUserbotSessionString] = useState('');
  const [whatsappUserbotClientLabel, setWhatsappUserbotClientLabel] = useState('');
  const [whatsappUserbotMode, setWhatsappUserbotMode] = useState('simple');
  const [whatsappUserbotAuthToken, setWhatsappUserbotAuthToken] = useState('');
  const [whatsappUserbotQrDataUrl, setWhatsappUserbotQrDataUrl] = useState('');
  const [isSendingWhatsappUserbotCode, setIsSendingWhatsappUserbotCode] = useState(false);
  const [isVerifyingWhatsappUserbotCode, setIsVerifyingWhatsappUserbotCode] = useState(false);
  const [isWhatsappUserbotVerified, setIsWhatsappUserbotVerified] = useState(false);
  const whatsappUserbotLastAuthStatusRef = useRef('');
  const [whatsappPhoneNumberId, setWhatsappPhoneNumberId] = useState('');
  const [whatsappAccessToken, setWhatsappAccessToken] = useState('');
  const [whatsappBusinessAccountId, setWhatsappBusinessAccountId] = useState('');
  const [whatsappVerifyToken, setWhatsappVerifyToken] = useState('');
  const detailsRequestIdRef = useRef(0);
  const { data: agents, isLoading, execute } = useAsync(
    () => agentService.getAll(),
    false
  );

  useEffect(() => {
    if (!isAuthenticated) return;
    execute();
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isChannelsModalOpen) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isChannelsModalOpen]);

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
    setChannels([]);
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
      setChannels(agent.channels || []);
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
          await loadAgentDetails(updatedAgents[0].id);
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

  const handleTogglePortraitFeature = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig =
      selectedAgent.template_config && typeof selectedAgent.template_config === 'object'
        ? selectedAgent.template_config
        : {};
    const nextConfig = {
      ...currentConfig,
      enable_chat_portrait: Boolean(enabled),
    };
    setIsSavingPortraitFeature(true);
    try {
      await agentService.update(selectedBotId, {
        template_config: nextConfig,
      });
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              template_config: nextConfig,
            }
          : prev
      );
      showSuccess(enabled ? 'Функция портрета включена' : 'Функция портрета отключена');
      await refreshAgents();
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку портрета');
    } finally {
      setIsSavingPortraitFeature(false);
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

  const handleCopyWidgetSnippet = async () => {
    if (!selectedAgent?.external_api_key) {
      showError('API ключ не найден');
      return;
    }
    const origin = window.location.origin;
    const snippet = `<script src="${origin}/api/agents/external/widget.js" data-rsd-widget="1" data-api-base="${origin}" data-api-key="${selectedAgent.external_api_key}" data-position="bottom-right" data-title="Онлайн-консультант"></script>`;
    try {
      await navigator.clipboard.writeText(snippet);
      showSuccess('Сниппет виджета скопирован');
    } catch {
      showError('Не удалось скопировать сниппет виджета');
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

  const resetChannelModalFields = () => {
    setBotTokenDraft('');
    setMakePrimaryChannel(false);
    setUserbotApiId('');
    setUserbotApiHash('');
    setUserbotPhone('');
    setUserbotCode('');
    setUserbotPassword('');
    setUserbotAuthToken('');
    setUserbotSessionString('');
    setIsSendingUserbotCode(false);
    setIsVerifyingUserbotCode(false);
    setWhatsappUserbotPhone('');
    setWhatsappUserbotSessionString('');
    setWhatsappUserbotClientLabel('');
    setWhatsappUserbotMode('simple');
    setWhatsappUserbotAuthToken('');
    setWhatsappUserbotQrDataUrl('');
    whatsappUserbotLastAuthStatusRef.current = '';
    setIsSendingWhatsappUserbotCode(false);
    setIsVerifyingWhatsappUserbotCode(false);
    setIsWhatsappUserbotVerified(false);
    setWhatsappPhoneNumberId('');
    setWhatsappAccessToken('');
    setWhatsappBusinessAccountId('');
    setWhatsappVerifyToken('');
  };

  const refreshChannels = async (botId) => {
    const data = await agentService.getChannels(botId);
    const list = data?.channels || [];
    setChannels(list);
    setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
    return list;
  };

  const handleOpenChannelsModal = async () => {
    if (!selectedBotId) {
      showError('Сначала выберите агента');
      return;
    }
    resetChannelModalFields();
    setChannelModalTab(selectedAgent?.template_type === 'sales_manager' ? 'userbot' : 'bot');
    setIsChannelsModalOpen(true);
    setIsLoadingChannels(true);
    try {
      await refreshChannels(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Не удалось загрузить каналы подключения');
    } finally {
      setIsLoadingChannels(false);
    }
  };

  const handleCloseChannelsModal = () => {
    setIsChannelsModalOpen(false);
    resetChannelModalFields();
  };

  const isSalesManagerTemplate = selectedAgent?.template_type === 'sales_manager';

  useEffect(() => {
    if (!isChannelsModalOpen || !isSalesManagerTemplate) return;
    if (channelModalTab !== 'userbot') {
      setChannelModalTab('userbot');
    }
  }, [channelModalTab, isChannelsModalOpen, isSalesManagerTemplate]);

  const handleRemoveChannel = async (connectionId) => {
    if (!selectedBotId) return;
    if (!window.confirm('Удалить этот канал подключения?')) return;
    setIsSavingChannel(true);
    try {
      const res = await agentService.removeChannel({ agent_id: selectedBotId, connection_id: connectionId });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('Канал успешно удален');
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при удалении канала');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddBotChannel = async () => {
    if (!selectedBotId) return;
    if (!botTokenDraft.trim()) {
      showError('Введите API ключ Telegram бота');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addBotChannel({
        agent_id: selectedBotId,
        bot_token: botTokenDraft.trim(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('Telegram бот подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении Telegram бота');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleRequestUserbotCode = async () => {
    if (!userbotApiId.trim() || !userbotApiHash.trim() || !userbotPhone.trim()) {
      showError('Заполните API ID, API hash и номер телефона');
      return;
    }
    setIsSendingUserbotCode(true);
    try {
      const response = await agentService.requestUserbotCode({
        api_id: Number(userbotApiId),
        api_hash: userbotApiHash.trim(),
        phone_number: userbotPhone.trim(),
      });
      setUserbotAuthToken(response?.auth_token || '');
      setUserbotSessionString('');
      showSuccess('Код подтверждения отправлен в Telegram');
    } catch (error) {
      showError(error?.message || 'Не удалось отправить код Telegram');
    } finally {
      setIsSendingUserbotCode(false);
    }
  };

  const handleVerifyUserbotCode = async () => {
    if (!userbotAuthToken) {
      showError('Сначала отправьте код подтверждения');
      return;
    }
    if (!userbotCode.trim()) {
      showError('Введите код из Telegram');
      return;
    }
    setIsVerifyingUserbotCode(true);
    try {
      const response = await agentService.verifyUserbotCode({
        auth_token: userbotAuthToken,
        code: userbotCode.trim(),
        password: userbotPassword.trim() || undefined,
      });
      setUserbotSessionString(response?.session_string || '');
      showSuccess('Код подтвержден, можно подключать userbot');
    } catch (error) {
      showError(error?.message || 'Не удалось подтвердить код');
    } finally {
      setIsVerifyingUserbotCode(false);
    }
  };

  const handleAddUserbotChannel = async () => {
    if (!selectedBotId) return;
    if (!userbotApiId.trim() || !userbotApiHash.trim()) {
      showError('Заполните API ID и API hash');
      return;
    }
    if (!userbotSessionString.trim()) {
      showError('Сначала подтвердите код Telegram и получите session string');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addUserbotChannel({
        agent_id: selectedBotId,
        api_id: Number(userbotApiId),
        api_hash: userbotApiHash.trim(),
        session_string: userbotSessionString.trim(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('Telegram userbot подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении userbot');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddWhatsAppBusinessApiChannel = async () => {
    if (!selectedBotId) return;
    if (!whatsappPhoneNumberId.trim()) {
      showError('Введите WhatsApp Phone Number ID');
      return;
    }
    if (!whatsappAccessToken.trim()) {
      showError('Введите WhatsApp Access Token');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addWhatsAppBusinessApiChannel({
        agent_id: selectedBotId,
        phone_number_id: whatsappPhoneNumberId.trim(),
        access_token: whatsappAccessToken.trim(),
        business_account_id: whatsappBusinessAccountId.trim() || undefined,
        verify_token: whatsappVerifyToken.trim() || undefined,
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('WhatsApp Business API канал подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении WhatsApp Business API');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddWhatsAppUserbotChannel = async () => {
    if (!selectedBotId) return;
    if (!whatsappUserbotPhone.trim()) {
      showError('Введите номер WhatsApp userbot');
      return;
    }
    if (whatsappUserbotMode === 'simple') {
      if (!whatsappUserbotSessionString.trim() || !isWhatsappUserbotVerified) {
        showError('Сначала подтвердите код и инициализируйте WhatsApp userbot-сессию');
        return;
      }
    } else if (!whatsappUserbotSessionString.trim()) {
      showError('Введите session string WhatsApp userbot');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addWhatsAppUserbotChannel({
        agent_id: selectedBotId,
        phone_number: whatsappUserbotPhone.trim(),
        session_string: whatsappUserbotSessionString.trim(),
        client_label: whatsappUserbotClientLabel.trim() || undefined,
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('WhatsApp userbot канал подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении WhatsApp userbot');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const switchWhatsappUserbotMode = (mode) => {
    setWhatsappUserbotMode(mode);
    setWhatsappUserbotAuthToken('');
    setWhatsappUserbotQrDataUrl('');
    setWhatsappUserbotSessionString('');
    setIsWhatsappUserbotVerified(false);
    whatsappUserbotLastAuthStatusRef.current = '';
  };

  const handleRequestWhatsappUserbotCode = async () => {
    if (!whatsappUserbotPhone.trim()) {
      showError('Введите номер WhatsApp userbot');
      return;
    }
    setIsSendingWhatsappUserbotCode(true);
    try {
      const response = await agentService.requestWhatsAppUserbotCode({
        phone_number: whatsappUserbotPhone.trim(),
      });
      setWhatsappUserbotAuthToken(response?.auth_token || '');
      setWhatsappUserbotQrDataUrl(response?.qr_data_url || '');
      setWhatsappUserbotSessionString('');
      setIsWhatsappUserbotVerified(false);
      whatsappUserbotLastAuthStatusRef.current = '';
      showSuccess(
        response?.hint || 'QR готов. Отсканируйте его в WhatsApp и затем нажмите «Проверить подключение».'
      );
    } catch (error) {
      showError(error?.message || 'Не удалось запросить QR-код WhatsApp');
    } finally {
      setIsSendingWhatsappUserbotCode(false);
    }
  };

  const handleVerifyWhatsappUserbotCode = async () => {
    if (!whatsappUserbotAuthToken) {
      showError('Сначала запросите код подтверждения WhatsApp');
      return;
    }
    setIsVerifyingWhatsappUserbotCode(true);
    try {
      const response = await agentService.verifyWhatsAppUserbotCode({
        auth_token: whatsappUserbotAuthToken,
      });
      setWhatsappUserbotSessionString(response?.session_string || '');
      if (response?.phone_number) {
        setWhatsappUserbotPhone(response.phone_number);
      }
      setIsWhatsappUserbotVerified(true);
      showSuccess('WhatsApp userbot успешно инициализирован');
    } catch (error) {
      setIsWhatsappUserbotVerified(false);
      showError(error?.message || 'Не удалось подтвердить код WhatsApp');
    } finally {
      setIsVerifyingWhatsappUserbotCode(false);
    }
  };

  useEffect(() => {
    if (whatsappUserbotMode !== 'simple') return undefined;
    if (!whatsappUserbotAuthToken) return undefined;
    if (isWhatsappUserbotVerified) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const response = await agentService.whatsappUserbotAuthStatus({
          auth_token: whatsappUserbotAuthToken,
        });
        if (cancelled) return;
        if (response?.qr_data_url) {
          setWhatsappUserbotQrDataUrl(response.qr_data_url);
        }
        const nextStatus = String(response?.status || '').trim().toLowerCase();
        const prevStatus = whatsappUserbotLastAuthStatusRef.current;
        if (nextStatus && nextStatus !== prevStatus) {
          if (nextStatus === 'paired') {
            showSuccess('QR подтвержден в WhatsApp. Нажмите «Проверить подключение».');
          } else if (nextStatus === 'failed') {
            showError(response?.last_error || 'Сессия WhatsApp завершилась с ошибкой. Запросите новый QR.');
          }
        }
        whatsappUserbotLastAuthStatusRef.current = nextStatus;
      } catch {
        // Ignore intermittent polling failures; user can still verify manually.
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [
    whatsappUserbotMode,
    whatsappUserbotAuthToken,
    isWhatsappUserbotVerified,
    showError,
    showSuccess,
  ]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const list = agents || [];
    if (list.length > 0 && !selectedBotId) {
      loadAgentDetails(list[0].id);
    }
  }, [agents, isAuthenticated, selectedBotId]);

  const selectedAgentName = useMemo(() => {
    if (!selectedAgent) return '';
    return selectedAgent.bot_username ? `@${selectedAgent.bot_username}` : `Агент #${selectedAgent.id}`;
  }, [selectedAgent]);
  const isWidgetSupportedTemplate = WIDGET_TEMPLATE_TYPES.has(
    String(selectedAgent?.template_type || 'qa').trim().toLowerCase()
  );
  const widgetSnippet = selectedAgent?.external_api_key
    ? `<script src="${window.location.origin}/api/agents/external/widget.js" data-rsd-widget="1" data-api-base="${window.location.origin}" data-api-key="${selectedAgent.external_api_key}" data-position="bottom-right" data-title="Онлайн-консультант"></script>`
    : '';

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
                  key={agent.id}
                  agent={agent}
                  isSelected={selectedBotId === agent.id}
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
                    <p>ID: {selectedAgent.id}</p>
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

                  {isWidgetSupportedTemplate ? (
                    <div className="agent-management-block">
                      <label>Виджет-коннектор для сайта</label>
                      <p className="docs-empty">
                        Вставьте этот `script` на сайт, и чат появится в углу экрана.
                      </p>
                      <textarea
                        rows="4"
                        className="input-main textarea"
                        value={widgetSnippet}
                        readOnly
                      />
                      <button
                        className="btn btn-black"
                        onClick={handleCopyWidgetSnippet}
                        title="Скопировать script сниппет"
                        aria-label="Copy widget snippet"
                      >
                        Скопировать сниппет виджета
                      </button>
                    </div>
                  ) : (
                    <div className="agent-management-block">
                      <label>Виджет-коннектор для сайта</label>
                      <p className="docs-empty">
                        Виджет доступен только для шаблонов: Консультант (QA) и Администратор CRM.
                      </p>
                    </div>
                  )}

                  <div className="agent-management-block">
                    <div className="docs-header-row">
                      <label>Каналы подключения</label>
                      <button type="button" className="btn btn-outline" onClick={handleOpenChannelsModal}>
                        Управлять каналами
                      </button>
                    </div>
                    {channels.length === 0 ? (
                      <p className="docs-empty">Каналы пока не подключены</p>
                    ) : (
                      <div className="docs-list-web">
                        {channels.map((channel) => (
                          <div key={channel.id} className="doc-row">
                            <div className="doc-meta">
                              <span className="doc-name">
                                {channelLabel(channel)} · {channel.external_id}
                              </span>
                              <span className={`doc-status ${channel.is_primary ? 'doc-status--ready' : ''}`}>
                                {channel.is_primary ? 'основной' : 'дополнительный'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="agent-management-block">
                    <label className="channel-primary-checkbox portrait-feature-toggle">
                      <input
                        type="checkbox"
                        checked={isPortraitFeatureEnabled(selectedAgent)}
                        onChange={(event) => handleTogglePortraitFeature(event.target.checked)}
                        disabled={isSavingPortraitFeature}
                      />
                      Включить функцию «Портрет чата»
                    </label>
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

      {isChannelsModalOpen && (
        <div className="auth-modal-backdrop channels-modal-backdrop">
          <div className="auth-modal channels-modal">
            <h3 className="auth-modal-title">Управление каналами подключения</h3>
            {isLoadingChannels ? (
              <p className="help-text">Загрузка каналов...</p>
            ) : (
              <div className="channels-modal__body">
                <div className="channel-modal-list">
                  {channels.length === 0 ? (
                    <p className="help-text">Подключений пока нет</p>
                  ) : (
                    channels.map((channel) => (
                      <div key={channel.id} className="doc-row">
                        <div className="doc-meta">
                          <span className="doc-name">
                            {channelLabel(channel)} · {channel.external_id}
                          </span>
                          <span className={`doc-status ${channel.is_primary ? 'doc-status--ready' : ''}`}>
                            {channel.is_primary ? 'основной' : 'дополнительный'}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="delete-btn"
                          disabled={isSavingChannel}
                          onClick={() => handleRemoveChannel(channel.id)}
                        >
                          ×
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <div className="connection-type-grid connection-type-grid--channels channels-tabs">
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'bot' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('bot')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    Telegram бот
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'userbot' ? 'active' : ''}`}
                    onClick={() => setChannelModalTab('userbot')}
                    disabled={isSavingChannel}
                  >
                    Telegram userbot
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'whatsapp_userbot' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('whatsapp_userbot')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    WhatsApp userbot
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card connection-type-card--with-beta ${channelModalTab === 'whatsapp' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('whatsapp')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    <span className="connection-type-card-label connection-type-card-label--stacked-wa-api">
                      <span className="connection-type-card-label__row">WhatsApp Business</span>
                      <span className="connection-type-card-label__row connection-type-card-label__row--api-beta">
                        API
                        <span className="beta-badge">BETA</span>
                      </span>
                    </span>
                  </button>
                </div>
                {isSalesManagerTemplate ? (
                  <p className="help-text">
                    Для шаблона "Менеджер продаж" доступно только подключение Telegram userbot.
                  </p>
                ) : null}

                {channelModalTab === 'bot' ? (
                  <div className="agent-management-block">
                    <input
                      type="text"
                      className="input-main"
                      placeholder="API ключ Telegram бота"
                      value={botTokenDraft}
                      onChange={(event) => setBotTokenDraft(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddBotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить Telegram бота'}
                    </button>
                  </div>
                ) : channelModalTab === 'userbot' ? (
                  <div className="agent-management-block">
                    <input
                      type="number"
                      className="input-main"
                      placeholder="API ID"
                      value={userbotApiId}
                      onChange={(event) => setUserbotApiId(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="API hash"
                      value={userbotApiHash}
                      onChange={(event) => setUserbotApiHash(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="+79990001122"
                      value={userbotPhone}
                      onChange={(event) => setUserbotPhone(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={handleRequestUserbotCode}
                      disabled={isSavingChannel || isSendingUserbotCode}
                    >
                      {isSendingUserbotCode ? 'Отправка...' : 'Отправить код'}
                    </button>
                    <input
                      type="text"
                      className="input-main"
                      placeholder="Код из Telegram"
                      value={userbotCode}
                      onChange={(event) => setUserbotCode(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="password"
                      className="input-main"
                      placeholder="Пароль 2FA (если есть)"
                      value={userbotPassword}
                      onChange={(event) => setUserbotPassword(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={handleVerifyUserbotCode}
                      disabled={isSavingChannel || isVerifyingUserbotCode}
                    >
                      {isVerifyingUserbotCode ? 'Проверка...' : 'Подтвердить код'}
                    </button>
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddUserbotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить Telegram userbot'}
                    </button>
                  </div>
                ) : channelModalTab === 'whatsapp_userbot' ? (
                  <div className="agent-management-block">
                    <div className="connection-type-grid connection-type-grid--pair channels-tabs">
                      <button
                        type="button"
                        className={`connection-type-card ${whatsappUserbotMode === 'simple' ? 'active' : ''}`}
                        onClick={() => switchWhatsappUserbotMode('simple')}
                        disabled={isSavingChannel}
                      >
                        Простое подключение
                      </button>
                      <button
                        type="button"
                        className={`connection-type-card ${whatsappUserbotMode === 'expert' ? 'active' : ''}`}
                        onClick={() => switchWhatsappUserbotMode('expert')}
                        disabled={isSavingChannel}
                      >
                        Режим эксперта
                      </button>
                    </div>

                    <input
                      type="text"
                      className="input-main"
                      placeholder="Номер WhatsApp userbot (+79990001122)"
                      value={whatsappUserbotPhone}
                      onChange={(event) => setWhatsappUserbotPhone(event.target.value)}
                      disabled={isSavingChannel}
                    />

                    {whatsappUserbotMode === 'simple' ? (
                      <>
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleRequestWhatsappUserbotCode}
                          disabled={isSavingChannel || isSendingWhatsappUserbotCode}
                        >
                          {isSendingWhatsappUserbotCode ? 'Отправка...' : 'Запросить QR-код'}
                        </button>
                        {whatsappUserbotQrDataUrl ? (
                          <div className="wa-qr-card">
                            <p className="wa-qr-title"><strong>QR для подключения</strong></p>
                            <img
                              src={whatsappUserbotQrDataUrl}
                              alt="WhatsApp QR"
                              className="wa-qr-image"
                            />
                            <p className="wa-qr-hint">
                              На телефоне: WhatsApp → Настройки → Связанные устройства → Привязать устройство — отсканируйте QR.
                            </p>
                          </div>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleVerifyWhatsappUserbotCode}
                          disabled={isSavingChannel || isVerifyingWhatsappUserbotCode}
                        >
                          {isVerifyingWhatsappUserbotCode ? 'Проверка...' : 'Проверить подключение'}
                        </button>
                      </>
                    ) : (
                      <textarea
                        className="input-main textarea"
                        rows={4}
                        placeholder="Session string WhatsApp userbot"
                        value={whatsappUserbotSessionString}
                        onChange={(event) => setWhatsappUserbotSessionString(event.target.value)}
                        disabled={isSavingChannel}
                      />
                    )}

                    <input
                      type="text"
                      className="input-main"
                      placeholder="Название клиента (опционально)"
                      value={whatsappUserbotClientLabel}
                      onChange={(event) => setWhatsappUserbotClientLabel(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddWhatsAppUserbotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить WhatsApp userbot'}
                    </button>
                    {whatsappUserbotMode === 'simple' && isWhatsappUserbotVerified ? (
                      <p className="help-text userbot-success">Сессия успешно инициализирована</p>
                    ) : null}
                  </div>
                ) : (
                  <div className="agent-management-block">
                    <input
                      type="text"
                      className="input-main"
                      placeholder="WhatsApp Phone Number ID"
                      value={whatsappPhoneNumberId}
                      onChange={(event) => setWhatsappPhoneNumberId(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="password"
                      className="input-main"
                      placeholder="WhatsApp Access Token"
                      value={whatsappAccessToken}
                      onChange={(event) => setWhatsappAccessToken(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="WhatsApp Business Account ID (опционально)"
                      value={whatsappBusinessAccountId}
                      onChange={(event) => setWhatsappBusinessAccountId(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="Webhook Verify Token (опционально)"
                      value={whatsappVerifyToken}
                      onChange={(event) => setWhatsappVerifyToken(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddWhatsAppBusinessApiChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить WhatsApp Business API'}
                    </button>
                  </div>
                )}

                <div className="auth-modal-actions">
                  <button type="button" className="btn btn-black" onClick={handleCloseChannelsModal}>
                    Закрыть
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
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