import React, { useEffect, useMemo, useRef, useState } from 'react';
import adminService from '../services/adminService';
import { ENV_CONFIG } from '../config/environment';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/managementPortal.css';

const ADMIN_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.ADMIN_TOKEN;

const MENU_ITEMS = [
  { id: 'overview', label: 'Обзор' },
  { id: 'users', label: 'Пользователи' },
  { id: 'agents', label: 'Агенты' },
  { id: 'chats', label: 'Чаты' },
  { id: 'turnkeyRequests', label: 'Заявки под ключ' },
  { id: 'errorReports', label: 'Сообщения об ошибках' },
  { id: 'billing', label: 'Тарифы' },
  { id: 'promoCodes', label: 'Промокоды' },
  { id: 'emailBroadcast', label: 'Email рассылка' },
  { id: 'contentPublisher', label: '📝 Контент' },
];

function formatError(error) {
  return (
    error?.response?.data?.detail
    || error?.message
    || 'Не удалось выполнить запрос к админ-панели'
  );
}

function formatChatChannel(channel) {
  const map = {
    telegram: 'Telegram Bot',
    telegram_userbot: 'Telegram Userbot',
    whatsapp_userbot: 'WhatsApp',
    external_api: 'External API',
    max_bot: 'MAX Bot',
    max_userbot: 'MAX Userbot',
    dashboard: 'Оператор',
  };
  return map[channel] || channel || '—';
}

const ManagementPortal = () => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [adminToken, setAdminToken] = useState(localStorage.getItem(ADMIN_TOKEN_KEY) || '');
  const [stats, setStats] = useState(null);
  const [activeSection, setActiveSection] = useState('overview');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  const [isLoadingTable, setIsLoadingTable] = useState(false);
  const [usersState, setUsersState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [agentsState, setAgentsState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [requestsState, setRequestsState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [errorReportsState, setErrorReportsState] = useState({
    items: [],
    page: 1,
    pageSize: 10,
    totalPages: 1,
    total: 0,
    search: '',
  });
  const [chatsState, setChatsState] = useState({
    items: [],
    page: 1,
    pageSize: 25,
    totalPages: 1,
    total: 0,
    search: '',
    agentId: '',
    agentUsername: '',
  });
  const [selectedChatKey, setSelectedChatKey] = useState(null);

  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [isSavingPlans, setIsSavingPlans] = useState(false);
  const [plansDraft, setPlansDraft] = useState([]);
  const [isLoadingPromoCodes, setIsLoadingPromoCodes] = useState(false);
  const [promoCodes, setPromoCodes] = useState([]);
  const [promoCodeDraft, setPromoCodeDraft] = useState({ code: '', discountPercent: 0 });
  const [actionInProgress, setActionInProgress] = useState(null);
  const [giftModal, setGiftModal] = useState({ open: false, user: null, planCode: 'Advanced' });
  const [broadcastDraft, setBroadcastDraft] = useState({ subject: '', body: '' });
  const [broadcastResult, setBroadcastResult] = useState(null);

  const targetedGroupIdRef = useRef(2);
  const [targetedGroups, setTargetedGroups] = useState([
    { id: 'g1', title: 'Группа 1', emailsRaw: '', selected: true },
  ]);
  const [targetedBroadcastDraft, setTargetedBroadcastDraft] = useState({ subject: '', body: '' });
  const [targetedIntervalSeconds, setTargetedIntervalSeconds] = useState(900);
  const [targetedPreview, setTargetedPreview] = useState(null);
  const [targetedJobStatus, setTargetedJobStatus] = useState(null);
  const [targetedJobId, setTargetedJobId] = useState(null);
  const [targetedPreviewLoading, setTargetedPreviewLoading] = useState(false);

  // --- Content Publisher state ---
  const [apTab, setApTab] = useState('settings');
  const [apSettings, setApSettings] = useState(null);
  const [apSettingsDraft, setApSettingsDraft] = useState({});
  const [apIsLoadingSettings, setApIsLoadingSettings] = useState(false);
  const [apIsSavingSettings, setApIsSavingSettings] = useState(false);
  const [apTopics, setApTopics] = useState([]);
  const [apTopicsTotal, setApTopicsTotal] = useState(0);
  const [apIsLoadingTopics, setApIsLoadingTopics] = useState(false);
  const [apNewTopicsText, setApNewTopicsText] = useState('');
  const [apImages, setApImages] = useState([]);
  const [apIsLoadingImages, setApIsLoadingImages] = useState(false);
  const [apJobs, setApJobs] = useState([]);
  const [apJobsTotal, setApJobsTotal] = useState(0);
  const [apIsLoadingJobs, setApIsLoadingJobs] = useState(false);
  const [apRunNowPlatform, setApRunNowPlatform] = useState('');
  const [apRunNowTopic, setApRunNowTopic] = useState('');
  const [apPreviewTopic, setApPreviewTopic] = useState('');
  const [apPreviewResult, setApPreviewResult] = useState(null);
  const [apActionInProgress, setApActionInProgress] = useState(null);
  const [apError, setApError] = useState('');
  const [apSuccess, setApSuccess] = useState('');

  const statsCards = useMemo(() => {
    if (!stats) return [];
    return [
      { key: 'users_total', title: 'Пользователи', value: stats.users_total ?? 0 },
      { key: 'agents_total', title: 'Агенты', value: stats.agents_total ?? 0 },
      { key: 'agents_active', title: 'Активные агенты', value: stats.agents_active ?? 0 },
      { key: 'documents_total', title: 'Документы', value: stats.documents_total ?? 0 },
      { key: 'paid_users_total', title: 'Платные пользователи', value: stats.paid_users_total ?? 0 },
      { key: 'payments_total', title: 'Платежи', value: stats.payments_total ?? 0 },
    ];
  }, [stats]);

  const planCards = useMemo(() => {
    const byPlan = stats?.users_by_plan ?? {};
    return [
      { key: 'free', title: 'Free', value: byPlan.Free ?? 0 },
      { key: 'advanced', title: 'Advanced', value: byPlan.Advanced ?? 0 },
      { key: 'pro', title: 'Pro', value: byPlan.Pro ?? 0 },
    ];
  }, [stats]);

  useEffect(() => {
    const fetchStats = async () => {
      if (!adminToken) {
        setStats(null);
        return;
      }
      try {
        setIsLoadingStats(true);
        setError('');
        const data = await adminService.getStats(adminToken);
        setStats(data);
      } catch (err) {
        setError(formatError(err));
        setStats(null);
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        setAdminToken('');
      } finally {
        setIsLoadingStats(false);
      }
    };

    fetchStats();
  }, [adminToken]);

  useEffect(() => {
    const fetchSectionData = async () => {
      if (!adminToken) return;
      if (
        activeSection !== 'users'
        && activeSection !== 'agents'
        && activeSection !== 'chats'
        && activeSection !== 'turnkeyRequests'
        && activeSection !== 'errorReports'
      ) return;

      try {
        setIsLoadingTable(true);
        setError('');
        if (activeSection === 'users') {
          const data = await adminService.getUsers(adminToken, {
            page: usersState.page,
            pageSize: usersState.pageSize,
            search: usersState.search,
          });
          setUsersState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'agents') {
          const data = await adminService.getAgents(adminToken, {
            page: agentsState.page,
            pageSize: agentsState.pageSize,
            search: agentsState.search,
          });
          setAgentsState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'turnkeyRequests') {
          const data = await adminService.getTurnkeyRequests(adminToken, {
            page: requestsState.page,
            pageSize: requestsState.pageSize,
            search: requestsState.search,
          });
          setRequestsState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'errorReports') {
          const data = await adminService.getErrorReports(adminToken, {
            page: errorReportsState.page,
            pageSize: errorReportsState.pageSize,
            search: errorReportsState.search,
          });
          setErrorReportsState((prev) => ({
            ...prev,
            items: data.items ?? [],
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
        } else if (activeSection === 'chats') {
          const data = await adminService.getChats(adminToken, {
            page: chatsState.page,
            pageSize: chatsState.pageSize,
            search: chatsState.search,
            agentId: chatsState.agentId ? Number(chatsState.agentId) : null,
            agentUsername: chatsState.agentUsername,
          });
          const nextItems = data.items ?? [];
          setChatsState((prev) => ({
            ...prev,
            items: nextItems,
            total: data.pagination?.total ?? 0,
            totalPages: data.pagination?.total_pages ?? 1,
          }));
          setSelectedChatKey((prev) => {
            if (prev && nextItems.some((item) => item.chat_key === prev)) return prev;
            return nextItems[0]?.chat_key ?? null;
          });
        }
      } catch (err) {
        setError(formatError(err));
      } finally {
        setIsLoadingTable(false);
      }
    };
    fetchSectionData();
  }, [
    activeSection,
    adminToken,
    usersState.page,
    usersState.pageSize,
    usersState.search,
    agentsState.page,
    agentsState.pageSize,
    agentsState.search,
    requestsState.page,
    requestsState.pageSize,
    requestsState.search,
    errorReportsState.page,
    errorReportsState.pageSize,
    errorReportsState.search,
    chatsState.page,
    chatsState.pageSize,
    chatsState.search,
    chatsState.agentId,
    chatsState.agentUsername,
  ]);

  useEffect(() => {
    if (!adminToken) return;
    if (activeSection !== 'billing') return;

    let cancelled = false;
    const fetchPlans = async () => {
      try {
        setIsLoadingPlans(true);
        setError('');
        const data = await adminService.getPlans(adminToken);
        const plans = Array.isArray(data?.plans) ? data.plans : [];
        if (cancelled) return;
        setPlansDraft(
          plans.map((p) => ({
            code: p?.code,
            title: p?.title || p?.code,
            price_rub_month: Number(p?.price_rub_month ?? 0),
            max_active_agents: Number(p?.max_active_agents ?? 0),
            knowledge_base_chunk_limit:
              p?.knowledge_base_chunk_limit === null ? null : Number(p?.knowledge_base_chunk_limit ?? 0),
          }))
        );
      } catch (err) {
        if (!cancelled) setError(formatError(err));
      } finally {
        if (!cancelled) setIsLoadingPlans(false);
      }
    };

    fetchPlans();
    return () => {
      cancelled = true;
    };
  }, [activeSection, adminToken]);

  useEffect(() => {
    if (!adminToken) return;
    if (activeSection !== 'promoCodes') return;

    let cancelled = false;
    const fetchPromoCodes = async () => {
      try {
        setIsLoadingPromoCodes(true);
        setError('');
        const data = await adminService.getPromoCodes(adminToken);
        if (cancelled) return;
        setPromoCodes(Array.isArray(data?.items) ? data.items : []);
      } catch (err) {
        if (!cancelled) setError(formatError(err));
      } finally {
        if (!cancelled) setIsLoadingPromoCodes(false);
      }
    };

    fetchPromoCodes();
    return () => {
      cancelled = true;
    };
  }, [activeSection, adminToken]);

  // --- Content Publisher effects ---
  useEffect(() => {
    if (!adminToken || activeSection !== 'contentPublisher') return;
    let cancelled = false;

    const load = async () => {
      setApError('');
      if (apTab === 'settings') {
        try {
          setApIsLoadingSettings(true);
          const data = await adminService.apGetSettings(adminToken);
          if (cancelled) return;
          const s = data.settings ?? {};
          setApSettings(s);
          setApSettingsDraft({
            posting_enabled: s.posting_enabled ?? false,
            posting_frequency_hours: s.posting_frequency_hours ?? 24,
            vcru_enabled: s.vcru_enabled ?? false,
            vcru_email: s.vcru_email ?? '',
            vcru_password: '',
            vcru_subsite_id: s.vcru_subsite_id ?? '',
            zen_enabled: s.zen_enabled ?? false,
            zen_login: s.zen_login ?? '',
            zen_password: '',
            zen_channel_id: s.zen_channel_id ?? '',
            auto_topics_enabled: s.auto_topics_enabled ?? true,
            topic_categories: (s.topic_categories ?? []).join(', '),
            promo_ratio: s.promo_ratio ?? 60,
            company_name: s.company_name ?? 'RSD AI',
            company_url: s.company_url ?? '',
            company_description: s.company_description ?? '',
            article_min_words: s.article_min_words ?? 600,
            article_max_words: s.article_max_words ?? 1500,
          });
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingSettings(false);
        }
      } else if (apTab === 'topics') {
        try {
          setApIsLoadingTopics(true);
          const data = await adminService.apGetTopics(adminToken);
          if (cancelled) return;
          setApTopics(data.items ?? []);
          setApTopicsTotal(data.total ?? 0);
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingTopics(false);
        }
      } else if (apTab === 'images') {
        try {
          setApIsLoadingImages(true);
          const data = await adminService.apGetImages(adminToken);
          if (cancelled) return;
          setApImages(data.items ?? []);
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingImages(false);
        }
      } else if (apTab === 'jobs') {
        try {
          setApIsLoadingJobs(true);
          const data = await adminService.apGetJobs(adminToken);
          if (cancelled) return;
          setApJobs(data.items ?? []);
          setApJobsTotal(data.total ?? 0);
        } catch (err) {
          if (!cancelled) setApError(formatError(err));
        } finally {
          if (!cancelled) setApIsLoadingJobs(false);
        }
      }
    };

    load();
    return () => { cancelled = true; };
  }, [activeSection, adminToken, apTab]);

  const handleApSaveSettings = async (e) => {
    e.preventDefault();
    try {
      setApIsSavingSettings(true);
      setApError('');
      setApSuccess('');
      const cats = (apSettingsDraft.topic_categories || '')
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean);
      const payload = {
        ...apSettingsDraft,
        topic_categories: cats,
      };
      if (!payload.vcru_password) delete payload.vcru_password;
      if (!payload.zen_password) delete payload.zen_password;
      const data = await adminService.apUpdateSettings(adminToken, payload);
      const s = data.settings ?? {};
      setApSettings(s);
      setApSuccess('Настройки сохранены');
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApIsSavingSettings(false);
    }
  };

  const handleApAddTopics = async (e) => {
    e.preventDefault();
    const lines = apNewTopicsText.split('\n').map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    try {
      setApActionInProgress('add-topics');
      setApError('');
      await adminService.apAddTopics(adminToken, lines);
      setApNewTopicsText('');
      const data = await adminService.apGetTopics(adminToken);
      setApTopics(data.items ?? []);
      setApTopicsTotal(data.total ?? 0);
      setApSuccess(`Добавлено тем: ${lines.length}`);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApGenerateTopics = async () => {
    try {
      setApActionInProgress('gen-topics');
      setApError('');
      const data = await adminService.apGenerateTopics(adminToken, { count: 10 });
      const refreshed = await adminService.apGetTopics(adminToken);
      setApTopics(refreshed.items ?? []);
      setApTopicsTotal(refreshed.total ?? 0);
      setApSuccess(`Сгенерировано тем: ${data.added ?? 0}`);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApDeleteTopic = async (id) => {
    if (!window.confirm('Удалить тему?')) return;
    try {
      setApActionInProgress(`del-topic-${id}`);
      setApError('');
      await adminService.apDeleteTopic(adminToken, id);
      setApTopics((prev) => prev.filter((t) => t.id !== id));
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApUploadImages = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    try {
      setApActionInProgress('upload-images');
      setApError('');
      for (const file of files) {
        await adminService.apUploadImage(adminToken, file);
      }
      const data = await adminService.apGetImages(adminToken);
      setApImages(data.items ?? []);
      setApSuccess(`Загружено изображений: ${files.length}`);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
      e.target.value = '';
    }
  };

  const handleApDeleteImage = async (id) => {
    if (!window.confirm('Удалить изображение?')) return;
    try {
      setApActionInProgress(`del-img-${id}`);
      setApError('');
      await adminService.apDeleteImage(adminToken, id);
      setApImages((prev) => prev.filter((img) => img.id !== id));
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApRunNow = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    try {
      setApActionInProgress('run-now');
      setApError('');
      setApSuccess('');
      const data = await adminService.apRunNow(adminToken, {
        platform: apRunNowPlatform || undefined,
        topic: apRunNowTopic || undefined,
      });
      setApSuccess(`Задача создана! job_id=${data.job_id}, платформа: ${data.platform}, тема: "${data.topic}"`);
      setApRunNowTopic('');
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleApPreview = async (e) => {
    e.preventDefault();
    if (!apPreviewTopic.trim()) return;
    try {
      setApActionInProgress('preview');
      setApError('');
      setApPreviewResult(null);
      const data = await adminService.apPreviewArticle(adminToken, {
        topic: apPreviewTopic.trim(),
        platform: 'vcru',
      });
      setApPreviewResult(data);
    } catch (err) {
      setApError(formatError(err));
    } finally {
      setApActionInProgress(null);
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    if (!login.trim() || !password) {
      setError('Введите логин и пароль администратора');
      return;
    }

    try {
      setIsSubmitting(true);
      setError('');
      const response = await adminService.login(login.trim(), password);
      const token = response?.access_token;
      if (!token) {
        setError('Сервер не вернул токен администратора');
        return;
      }
      localStorage.setItem(ADMIN_TOKEN_KEY, token);
      setAdminToken(token);
      setPassword('');
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    setAdminToken('');
    setStats(null);
    setError('');
    setPassword('');
  };

  const handleSavePlans = async () => {
    try {
      setIsSavingPlans(true);
      setError('');

      const payloadPlans = (plansDraft || []).map((p) => ({
        code: p.code,
        price_rub_month: Number(p.price_rub_month ?? 0),
        max_active_agents: Number(p.max_active_agents ?? 0),
        knowledge_base_chunk_limit:
          p.knowledge_base_chunk_limit === null ? null : Number(p.knowledge_base_chunk_limit ?? 0),
      }));

      const data = await adminService.updatePlans(adminToken, payloadPlans);
      const updatedPlans = Array.isArray(data?.plans) ? data.plans : [];
      setPlansDraft(
        updatedPlans.map((p) => ({
          code: p?.code,
          title: p?.title || p?.code,
          price_rub_month: Number(p?.price_rub_month ?? 0),
          max_active_agents: Number(p?.max_active_agents ?? 0),
          knowledge_base_chunk_limit:
            p?.knowledge_base_chunk_limit === null
              ? null
              : Number(p?.knowledge_base_chunk_limit ?? 0),
        }))
      );
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsSavingPlans(false);
    }
  };

  const refreshUsers = async () => {
    try {
      setIsLoadingTable(true);
      setError('');
      const data = await adminService.getUsers(adminToken, {
        page: usersState.page,
        pageSize: usersState.pageSize,
        search: usersState.search,
      });
      setUsersState((prev) => ({
        ...prev,
        items: data.items ?? [],
        total: data.pagination?.total ?? 0,
        totalPages: data.pagination?.total_pages ?? 1,
      }));
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsLoadingTable(false);
    }
  };

  const handleBanUser = async (user) => {
    const action = user.is_banned ? 'unban' : 'ban';
    const confirmMsg = user.is_banned
      ? `Разблокировать пользователя "${user.name}"?`
      : `Заблокировать пользователя "${user.name}"? Все агенты будут удалены.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setActionInProgress(user.id);
      setError('');
      if (action === 'ban') {
        await adminService.banUser(adminToken, user.id);
      } else {
        await adminService.unbanUser(adminToken, user.id);
      }
      await refreshUsers();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleGiftSubscription = async () => {
    const { user, planCode } = giftModal;
    if (!user || !planCode) return;

    try {
      setActionInProgress(user.id);
      setError('');
      await adminService.giftSubscription(adminToken, user.id, planCode);
      setGiftModal({ open: false, user: null, planCode: 'Advanced' });
      await refreshUsers();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const refreshPromoCodes = async () => {
    try {
      setIsLoadingPromoCodes(true);
      setError('');
      const data = await adminService.getPromoCodes(adminToken);
      setPromoCodes(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsLoadingPromoCodes(false);
    }
  };

  const handleCreatePromoCode = async (event) => {
    event.preventDefault();
    const code = promoCodeDraft.code.trim().toUpperCase();
    const discountPercent = Number(promoCodeDraft.discountPercent);
    if (!code) {
      setError('Введите промокод');
      return;
    }
    if (Number.isNaN(discountPercent) || discountPercent < 0 || discountPercent > 100) {
      setError('Скидка должна быть от 0 до 100');
      return;
    }

    try {
      setActionInProgress('promo-create');
      setError('');
      await adminService.createPromoCode(adminToken, {
        code,
        discount_percent: discountPercent,
      });
      setPromoCodeDraft({ code: '', discountPercent: 0 });
      await refreshPromoCodes();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDeletePromoCode = async (promoCodeItem) => {
    if (!window.confirm(`Удалить промокод "${promoCodeItem.code}"?`)) return;

    try {
      setActionInProgress(`promo-delete-${promoCodeItem.id}`);
      setError('');
      await adminService.deletePromoCode(adminToken, promoCodeItem.id);
      await refreshPromoCodes();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleSendEmailBroadcast = async (event) => {
    event.preventDefault();
    const subject = broadcastDraft.subject.trim();
    const body = broadcastDraft.body.trim();
    if (subject.length < 3) {
      setError('Тема письма должна быть не короче 3 символов');
      return;
    }
    if (body.length < 10) {
      setError('Текст рассылки должен быть не короче 10 символов');
      return;
    }
    if (!window.confirm('Запустить email-рассылку по подтвержденным пользователям?')) {
      return;
    }

    try {
      setActionInProgress('email-broadcast');
      setError('');
      const result = await adminService.sendEmailBroadcast(adminToken, { subject, body });
      setBroadcastResult(result);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  useEffect(() => {
    if (!targetedJobId || !adminToken) {
      return undefined;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const job = await adminService.getEmailTargetedBroadcastJob(adminToken, targetedJobId);
        if (cancelled) return;
        setTargetedJobStatus(job);
        if (job.status === 'completed' || job.status === 'failed') {
          setTargetedJobId(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(formatError(err));
          setTargetedJobId(null);
        }
      }
    };
    poll();
    const interval = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [targetedJobId, adminToken]);

  const addTargetedGroup = () => {
    const n = targetedGroupIdRef.current;
    targetedGroupIdRef.current = n + 1;
    setTargetedGroups((prev) => [
      ...prev,
      { id: `g${n}`, title: `Группа ${n}`, emailsRaw: '', selected: true },
    ]);
  };

  const removeTargetedGroup = (groupId) => {
    setTargetedGroups((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((g) => g.id !== groupId);
    });
  };

  const buildTargetedPayload = () => {
    const groups = targetedGroups.map((g) => ({
      title: g.title.trim(),
      emails_raw: g.emailsRaw,
    }));
    const selected_titles = targetedGroups
      .filter((g) => g.selected && g.title.trim())
      .map((g) => g.title.trim());
    return { groups, selected_titles };
  };

  const handleTargetedPreview = async (event) => {
    event.preventDefault();
    const { groups, selected_titles } = buildTargetedPayload();
    if (!selected_titles.length) {
      setError('Отметьте хотя бы одну группу с непустым названием');
      return;
    }
    const emptyTitle = groups.some((g) => !g.title);
    if (emptyTitle) {
      setError('У каждой группы должно быть название');
      return;
    }
    try {
      setTargetedPreviewLoading(true);
      setError('');
      const data = await adminService.previewEmailTargeted(adminToken, { groups, selected_titles });
      setTargetedPreview(data);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setTargetedPreviewLoading(false);
    }
  };

  const handleTargetedSend = async (event) => {
    event.preventDefault();
    const subject = targetedBroadcastDraft.subject.trim();
    const body = targetedBroadcastDraft.body.trim();
    if (subject.length < 3) {
      setError('Тема письма (точечная рассылка) — не короче 3 символов');
      return;
    }
    if (body.length < 10) {
      setError('Текст письма — не короче 10 символов');
      return;
    }
    const interval = Number(targetedIntervalSeconds);
    if (Number.isNaN(interval) || interval < 30) {
      setError('Интервал между письмами — не меньше 30 секунд');
      return;
    }
    const { groups, selected_titles } = buildTargetedPayload();
    if (!selected_titles.length) {
      setError('Отметьте хотя бы одну группу');
      return;
    }
    if (groups.some((g) => !g.title)) {
      setError('У каждой группы должно быть название');
      return;
    }
    if (
      !window.confirm(
        `Запустить точечную рассылку? Получатели: после разбора списков — смотрите превью. Пауза между письмами: ${interval} с.`
      )
    ) {
      return;
    }
    try {
      setActionInProgress('email-targeted');
      setError('');
      setTargetedJobStatus(null);
      const result = await adminService.sendEmailTargetedBroadcast(adminToken, {
        groups,
        selected_titles,
        subject,
        body,
        interval_seconds: Math.min(Math.max(Math.round(interval), 30), 86400),
      });
      setTargetedJobId(result.job_id);
      setTargetedPreview((prev) => ({
        ...(prev || {}),
        unique_total: result.total_recipients,
        per_group: result.preview?.per_group || prev?.per_group,
      }));
    } catch (err) {
      setError(formatError(err));
    } finally {
      setActionInProgress(null);
    }
  };

  const renderOverview = () => (
    <>
      <div className="management-content-head">
        <h2>Сводная статистика</h2>
        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoadingStats}
          onClick={async () => {
            try {
              setIsLoadingStats(true);
              setError('');
              const data = await adminService.getStats(adminToken);
              setStats(data);
            } catch (err) {
              setError(formatError(err));
            } finally {
              setIsLoadingStats(false);
            }
          }}
        >
          Обновить
        </button>
      </div>

      {error && <div className="management-error">{error}</div>}

      {isLoadingStats ? (
        <p>Загрузка статистики...</p>
      ) : (
        <>
          <div className="management-stats-grid">
            {statsCards.map((card) => (
              <article key={card.key} className="management-stat-card">
                <span>{card.title}</span>
                <strong>{card.value}</strong>
              </article>
            ))}
          </div>
          <h3 className="management-section-title">Пользователи по тарифам</h3>
          <div className="management-stats-grid management-plan-grid">
            {planCards.map((card) => (
              <article key={card.key} className="management-stat-card">
                <span>{card.title}</span>
                <strong>{card.value}</strong>
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );

  const renderUsers = () => (
    <>
      <div className="management-content-head">
        <h2>Пользователи</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по имени или Telegram ID"
            value={usersState.search}
            onChange={(e) => setUsersState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка пользователей...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Имя</th>
                  <th>Telegram ID</th>
                  <th>Тариф</th>
                  <th>Подписка до</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {usersState.items.map((user) => (
                  <tr key={user.id} className={user.is_banned ? 'management-row-banned' : ''}>
                    <td>{user.id}</td>
                    <td>{user.name}</td>
                    <td>{user.telegram_id ?? '-'}</td>
                    <td>{user.subscription_type}</td>
                    <td>
                      {user.subscription_end_date
                        ? new Date(user.subscription_end_date).toLocaleDateString()
                        : '-'}
                    </td>
                    <td>
                      {user.is_banned
                        ? <span className="management-badge management-badge-banned">Заблокирован</span>
                        : <span className="management-badge management-badge-active">Активен</span>}
                    </td>
                    <td className="management-actions-cell">
                      <button
                        type="button"
                        className={`btn btn-sm ${user.is_banned ? 'btn-outline' : 'btn-danger'}`}
                        disabled={actionInProgress === user.id}
                        onClick={() => handleBanUser(user)}
                      >
                        {actionInProgress === user.id ? '...' : user.is_banned ? 'Разбан' : 'Бан'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline"
                        disabled={actionInProgress === user.id || user.is_banned}
                        onClick={() => setGiftModal({ open: true, user, planCode: 'Advanced' })}
                      >
                        Подарить
                      </button>
                    </td>
                  </tr>
                ))}
                {usersState.items.length === 0 && (
                  <tr><td colSpan={7}>Ничего не найдено</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={usersState.page <= 1}
              onClick={() => setUsersState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {usersState.page} из {usersState.totalPages} (всего: {usersState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={usersState.page >= usersState.totalPages}
              onClick={() => setUsersState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}

      {giftModal.open && (
        <div className="management-modal-overlay" onClick={() => setGiftModal({ open: false, user: null, planCode: 'Advanced' })}>
          <div className="management-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Подарить подписку</h3>
            <p>Пользователь: <strong>{giftModal.user?.name}</strong> (ID: {giftModal.user?.id})</p>
            <div className="management-form-row">
              <label>Тариф</label>
              <select
                value={giftModal.planCode}
                onChange={(e) => setGiftModal((prev) => ({ ...prev, planCode: e.target.value }))}
              >
                <option value="Advanced">Advanced</option>
                <option value="Pro">Pro</option>
              </select>
            </div>
            <p className="management-modal-hint">Подписка будет продлена на 30 дней от текущей даты окончания (или от сегодня).</p>
            <div className="management-modal-buttons">
              <button
                type="button"
                className="btn btn-black"
                disabled={actionInProgress === giftModal.user?.id}
                onClick={handleGiftSubscription}
              >
                {actionInProgress === giftModal.user?.id ? 'Оформляю...' : 'Подарить'}
              </button>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setGiftModal({ open: false, user: null, planCode: 'Advanced' })}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  const renderAgents = () => (
    <>
      <div className="management-content-head">
        <h2>Агенты</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по username, owner, bot_id"
            value={agentsState.search}
            onChange={(e) => setAgentsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка агентов...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Bot ID</th>
                  <th>Username</th>
                  <th>Владелец</th>
                  <th>Тариф</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {agentsState.items.map((agent) => (
                  <tr key={agent.id}>
                    <td>{agent.id}</td>
                    <td>{agent.bot_id ?? '-'}</td>
                    <td>{agent.bot_username ?? '-'}</td>
                    <td>{agent.owner_name}</td>
                    <td>{agent.owner_subscription_type}</td>
                    <td>{agent.is_active ? 'Активен' : 'Выключен'}</td>
                  </tr>
                ))}
                {agentsState.items.length === 0 && (
                  <tr><td colSpan={6}>Ничего не найдено</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={agentsState.page <= 1}
              onClick={() => setAgentsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {agentsState.page} из {agentsState.totalPages} (всего: {agentsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={agentsState.page >= agentsState.totalPages}
              onClick={() => setAgentsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const selectedChat = chatsState.items.find((item) => item.chat_key === selectedChatKey) || null;

  const renderChats = () => (
    <>
      <div className="management-content-head">
        <h2>Чаты всех агентов</h2>
        <div className="management-inline-controls management-inline-controls-grid">
          <input
            type="text"
            placeholder="Поиск по пользователю, username агента или external_id"
            value={chatsState.search}
            onChange={(e) => setChatsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
          <input
            type="number"
            min={1}
            placeholder="ID агента"
            value={chatsState.agentId}
            onChange={(e) => setChatsState((prev) => ({ ...prev, page: 1, agentId: e.target.value }))}
          />
          <input
            type="text"
            placeholder="Username агента"
            value={chatsState.agentUsername}
            onChange={(e) => setChatsState((prev) => ({ ...prev, page: 1, agentUsername: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка чатов...</p> : (
        <>
          <div className="management-chats-layout">
            <aside className="management-chats-list">
              {chatsState.items.length === 0 ? (
                <p className="management-chat-empty">Чаты не найдены</p>
              ) : (
                chatsState.items.map((chat) => (
                  <button
                    key={chat.chat_key}
                    type="button"
                    className={`management-chat-item ${selectedChatKey === chat.chat_key ? 'active' : ''}`}
                    onClick={() => setSelectedChatKey(chat.chat_key)}
                  >
                    <div className="management-chat-item-top">
                      <strong>{chat.user_display_name || `User ${chat.user_external_id}`}</strong>
                      {chat.is_frozen ? <span className="management-badge management-badge-banned">Заморожен</span> : null}
                    </div>
                    <div className="management-chat-item-meta">
                      <span>@{chat.agent_bot_username || 'unknown_agent'} · {formatChatChannel(chat.chat_channel)}</span>
                      <span>{chat.last_message_at ? new Date(chat.last_message_at).toLocaleString() : '—'}</span>
                    </div>
                  </button>
                ))
              )}
            </aside>
            <section className="management-chat-thread">
              {!selectedChat ? (
                <p className="management-chat-empty">Выберите чат слева для просмотра переписки</p>
              ) : (
                <>
                  <div className="management-chat-thread-head">
                    <div className="management-cell-stack">
                      <strong>{selectedChat.user_display_name || `User ${selectedChat.user_external_id}`}</strong>
                      <span className="management-cell-muted">
                        Агент: @{selectedChat.agent_bot_username || 'unknown_agent'} ·
                        {' '}
                        {formatChatChannel(selectedChat.chat_channel)}
                        {' '}
                        · external_id:
                        {' '}
                        {selectedChat.user_external_id}
                      </span>
                    </div>
                    <span className="management-cell-muted">
                      Сообщений пользователя:
                      {' '}
                      {selectedChat.questions_count ?? 0}
                    </span>
                  </div>
                  <div className="management-chat-messages">
                    {(selectedChat.messages || []).length === 0 ? (
                      <p className="management-chat-empty">Сообщений в чате пока нет</p>
                    ) : (
                      selectedChat.messages.map((message, index) => (
                        <article
                          key={`${selectedChat.chat_key}-${index}-${message.created_at || 'no-time'}`}
                          className={`management-chat-message ${message.role === 'user' ? 'user' : 'operator'}`}
                        >
                          <header>
                            <span>
                              {message.role === 'user' ? 'Пользователь' : message.role === 'operator' ? 'Оператор' : 'Агент'}
                              {' '}
                              ·
                              {' '}
                              {formatChatChannel(message.channel)}
                            </span>
                            <time>{message.created_at ? new Date(message.created_at).toLocaleString() : '—'}</time>
                          </header>
                          <p>{message.text || '—'}</p>
                        </article>
                      ))
                    )}
                  </div>
                </>
              )}
            </section>
          </div>

          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={chatsState.page <= 1}
              onClick={() => setChatsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {chatsState.page} из {chatsState.totalPages} (всего: {chatsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={chatsState.page >= chatsState.totalPages}
              onClick={() => setChatsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const renderErrorReports = () => (
    <>
      <div className="management-content-head">
        <h2>Сообщения об ошибках</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по тексту, имени или email"
            value={errorReportsState.search}
            onChange={(e) => setErrorReportsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка сообщений...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table management-table-wrap-text">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Дата</th>
                  <th>Пользователь</th>
                  <th>Описание</th>
                </tr>
              </thead>
              <tbody>
                {errorReportsState.items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.created_at ? new Date(row.created_at).toLocaleString() : '-'}</td>
                    <td>
                      <div className="management-cell-stack">
                        <span>{row.user?.name ?? '—'}</span>
                        <span className="management-cell-muted">{row.user?.email || '—'}</span>
                      </div>
                    </td>
                    <td>{row.description}</td>
                  </tr>
                ))}
                {errorReportsState.items.length === 0 && (
                  <tr><td colSpan={4}>Сообщений пока нет</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={errorReportsState.page <= 1}
              onClick={() => setErrorReportsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {errorReportsState.page} из {errorReportsState.totalPages} (всего: {errorReportsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={errorReportsState.page >= errorReportsState.totalPages}
              onClick={() => setErrorReportsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const renderTurnkeyRequests = () => (
    <>
      <div className="management-content-head">
        <h2>Заявки по тарифу «Агент под ключ»</h2>
        <div className="management-inline-controls">
          <input
            type="text"
            placeholder="Поиск по телефону, email или тексту заявки"
            value={requestsState.search}
            onChange={(e) => setRequestsState((prev) => ({ ...prev, page: 1, search: e.target.value }))}
          />
        </div>
      </div>
      {error && <div className="management-error">{error}</div>}
      {isLoadingTable ? <p>Загрузка заявок...</p> : (
        <>
          <div className="management-table-wrap">
            <table className="management-table management-table-wrap-text">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Дата</th>
                  <th>Телефон</th>
                  <th>Email</th>
                  <th>Запрос</th>
                </tr>
              </thead>
              <tbody>
                {requestsState.items.map((request) => (
                  <tr key={request.id}>
                    <td>{request.id}</td>
                    <td>{request.created_at ? new Date(request.created_at).toLocaleString() : '-'}</td>
                    <td>{request.phone_number}</td>
                    <td>{request.email}</td>
                    <td>{request.requested_agent || request.purpose}</td>
                  </tr>
                ))}
                {requestsState.items.length === 0 && (
                  <tr><td colSpan={5}>Заявок пока нет</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="management-pagination">
            <button
              type="button"
              className="btn btn-outline"
              disabled={requestsState.page <= 1}
              onClick={() => setRequestsState((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Назад
            </button>
            <span>Стр. {requestsState.page} из {requestsState.totalPages} (всего: {requestsState.total})</span>
            <button
              type="button"
              className="btn btn-outline"
              disabled={requestsState.page >= requestsState.totalPages}
              onClick={() => setRequestsState((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </>
  );

  const renderBilling = () => (
    <>
      <div className="management-content-head">
        <h2>Тарифы</h2>
        <button
          type="button"
          className="btn btn-outline"
          disabled={isSavingPlans || isLoadingPlans || (plansDraft || []).length === 0}
          onClick={handleSavePlans}
        >
          Сохранить изменения
        </button>
      </div>

      {error && <div className="management-error">{error}</div>}

      {isLoadingPlans ? (
        <p>Загрузка тарифов...</p>
      ) : (
        <div className="management-plans-editor">
          {(plansDraft || []).map((plan) => {
            const kbUnlimited = plan.knowledge_base_chunk_limit === null;
            return (
              <article key={plan.code} className="management-plan-editor-card">
                <h3>{plan.title}</h3>

                <div className="management-form-row">
                  <label>Цена (руб/мес)</label>
                  <input
                    type="number"
                    min={0}
                    value={plan.price_rub_month}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setPlansDraft((prev) =>
                        prev.map((p) =>
                          p.code === plan.code ? { ...p, price_rub_month: Number.isNaN(val) ? 0 : val } : p
                        )
                      );
                    }}
                  />
                </div>

                <div className="management-form-row">
                  <label>Макс. активных агентов</label>
                  <input
                    type="number"
                    min={0}
                    value={plan.max_active_agents}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setPlansDraft((prev) =>
                        prev.map((p) =>
                          p.code === plan.code ? { ...p, max_active_agents: Number.isNaN(val) ? 0 : val } : p
                        )
                      );
                    }}
                  />
                </div>

                <div className="management-form-row">
                  <label className="management-checkbox">
                    <input
                      type="checkbox"
                      checked={kbUnlimited}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setPlansDraft((prev) =>
                          prev.map((p) => {
                            if (p.code !== plan.code) return p;
                            if (checked) return { ...p, knowledge_base_chunk_limit: null };
                            // If leaving unlimited mode, restore a sane default.
                            return {
                              ...p,
                              knowledge_base_chunk_limit: p.knowledge_base_chunk_limit ?? 100,
                            };
                          })
                        );
                      }}
                    />
                    Безлимит базы знаний
                  </label>

                  <input
                    type="number"
                    min={0}
                    disabled={kbUnlimited}
                    value={kbUnlimited ? '' : plan.knowledge_base_chunk_limit ?? 0}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setPlansDraft((prev) =>
                        prev.map((p) =>
                          p.code === plan.code
                            ? { ...p, knowledge_base_chunk_limit: Number.isNaN(val) ? 0 : val }
                            : p
                        )
                      );
                    }}
                    placeholder="Лимит чанков"
                  />
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );

  const renderPromoCodes = () => (
    <>
      <div className="management-content-head">
        <h2>Промокоды</h2>
        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoadingPromoCodes || actionInProgress === 'promo-create'}
          onClick={refreshPromoCodes}
        >
          Обновить
        </button>
      </div>
      {error && <div className="management-error">{error}</div>}

      <form className="management-promo-form" onSubmit={handleCreatePromoCode}>
        <div className="management-form-row">
          <label htmlFor="promo-code-input">Промокод</label>
          <input
            id="promo-code-input"
            type="text"
            placeholder="Например: SPRING50"
            value={promoCodeDraft.code}
            maxLength={64}
            onChange={(e) => setPromoCodeDraft((prev) => ({ ...prev, code: e.target.value.toUpperCase() }))}
          />
        </div>
        <div className="management-form-row">
          <label htmlFor="promo-discount-input">Скидка (%)</label>
          <input
            id="promo-discount-input"
            type="number"
            min={0}
            max={100}
            value={promoCodeDraft.discountPercent}
            onChange={(e) => setPromoCodeDraft((prev) => ({ ...prev, discountPercent: e.target.value }))}
          />
        </div>
        <button
          type="submit"
          className="btn btn-black"
          disabled={actionInProgress === 'promo-create'}
        >
          {actionInProgress === 'promo-create' ? 'Создание...' : 'Добавить промокод'}
        </button>
      </form>

      {isLoadingPromoCodes ? (
        <p>Загрузка промокодов...</p>
      ) : (
        <div className="management-table-wrap">
          <table className="management-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Код</th>
                <th>Скидка</th>
                <th>Создан</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {promoCodes.map((promoCodeItem) => (
                <tr key={promoCodeItem.id}>
                  <td>{promoCodeItem.id}</td>
                  <td>{promoCodeItem.code}</td>
                  <td>{promoCodeItem.discount_percent}%</td>
                  <td>
                    {promoCodeItem.created_at
                      ? new Date(promoCodeItem.created_at).toLocaleString()
                      : '-'}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      disabled={actionInProgress === `promo-delete-${promoCodeItem.id}`}
                      onClick={() => handleDeletePromoCode(promoCodeItem)}
                    >
                      {actionInProgress === `promo-delete-${promoCodeItem.id}` ? '...' : 'Удалить'}
                    </button>
                  </td>
                </tr>
              ))}
              {promoCodes.length === 0 && (
                <tr><td colSpan={5}>Промокодов пока нет</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  const renderContentPublisher = () => {
    const AP_TABS = [
      { id: 'settings', label: 'Настройки' },
      { id: 'topics', label: 'Темы' },
      { id: 'images', label: 'Изображения' },
      { id: 'jobs', label: 'История' },
      { id: 'run', label: 'Запуск / Превью' },
    ];

    const statusLabel = (s) => ({
      pending: 'Ожидает',
      generating: 'Генерация',
      publishing: 'Публикация',
      published: 'Опубликовано',
      failed: 'Ошибка',
    }[s] || s);

    const statusClass = (s) => ({
      published: 'management-badge-success',
      failed: 'management-badge-danger',
      generating: 'management-badge-info',
      publishing: 'management-badge-info',
    }[s] || 'management-badge-muted');

    return (
      <>
        <div className="management-content-head">
          <h2>Контент — автопубликация статей</h2>
          <button
            type="button"
            className="btn btn-black"
            disabled={apActionInProgress === 'run-now'}
            onClick={handleApRunNow}
            title="Запустить автопубликацию сразу, без ожидания окна времени"
          >
            {apActionInProgress === 'run-now' ? 'Запуск...' : 'Выпустить статью сейчас'}
          </button>
        </div>

        {apError && <div className="management-error">{apError}</div>}
        {apSuccess && <div className="management-success">{apSuccess}</div>}

        <div className="ap-tabs">
          {AP_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`ap-tab-btn ${apTab === tab.id ? 'active' : ''}`}
              onClick={() => { setApTab(tab.id); setApError(''); setApSuccess(''); }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* SETTINGS TAB */}
        {apTab === 'settings' && (
          <div className="ap-panel">
            {apIsLoadingSettings ? <p>Загрузка настроек...</p> : (
              <form onSubmit={handleApSaveSettings} className="ap-settings-form">
                <section className="ap-section">
                  <h3>Расписание публикаций</h3>
                  <div className="management-form-row">
                    <label className="management-checkbox">
                      <input
                        type="checkbox"
                        checked={apSettingsDraft.posting_enabled ?? false}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, posting_enabled: e.target.checked }))}
                      />
                      Автопубликация включена
                    </label>
                  </div>
                  <div className="management-form-row">
                    <label>Частота (часов между постами)</label>
                    <input
                      type="number"
                      min={1}
                      max={720}
                      value={apSettingsDraft.posting_frequency_hours ?? 24}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, posting_frequency_hours: Number(e.target.value) }))}
                    />
                  </div>
                </section>

                <section className="ap-section">
                  <h3>Платформы</h3>

                  <div className="ap-platform-block">
                    <h4>vc.ru</h4>
                    <div className="management-form-row">
                      <label className="management-checkbox">
                        <input
                          type="checkbox"
                          checked={apSettingsDraft.vcru_enabled ?? false}
                          onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_enabled: e.target.checked }))}
                        />
                        Включить vc.ru
                      </label>
                    </div>
                    <div className="management-form-row">
                      <label>Email аккаунта</label>
                      <input
                        type="email"
                        placeholder="user@example.com"
                        value={apSettingsDraft.vcru_email ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_email: e.target.value }))}
                      />
                    </div>
                    <div className="management-form-row">
                      <label>
                        Пароль
                        {apSettings?.vcru_has_password && (
                          <span className="ap-hint"> (уже задан, оставьте пустым чтобы не менять)</span>
                        )}
                      </label>
                      <input
                        type="password"
                        placeholder={apSettings?.vcru_has_password ? '••••••••' : 'Пароль'}
                        value={apSettingsDraft.vcru_password ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_password: e.target.value }))}
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="management-form-row">
                      <label>Subsite ID (необязательно)</label>
                      <input
                        type="text"
                        placeholder="ID раздела/субсайта"
                        value={apSettingsDraft.vcru_subsite_id ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, vcru_subsite_id: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="ap-platform-block">
                    <h4>Яндекс Дзен (dzen.ru)</h4>
                    <div className="management-form-row">
                      <label className="management-checkbox">
                        <input
                          type="checkbox"
                          checked={apSettingsDraft.zen_enabled ?? false}
                          onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_enabled: e.target.checked }))}
                        />
                        Включить Яндекс Дзен
                      </label>
                    </div>
                    <div className="management-form-row">
                      <label>
                        Логин Яндекс
                      </label>
                      <input
                        type="text"
                        placeholder="login@yandex.ru"
                        value={apSettingsDraft.zen_login ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_login: e.target.value }))}
                      />
                    </div>
                    <div className="management-form-row">
                      <label>
                        Пароль Яндекс
                        {apSettings?.zen_has_password && (
                          <span className="ap-hint"> (уже задан, оставьте пустым чтобы не менять)</span>
                        )}
                      </label>
                      <input
                        type="password"
                        placeholder={apSettings?.zen_has_password ? '••••••••' : 'Пароль Яндекс'}
                        value={apSettingsDraft.zen_password ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_password: e.target.value }))}
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="management-form-row">
                      <label>Channel ID (необязательно)</label>
                      <input
                        type="text"
                        placeholder="ID вашего канала"
                        value={apSettingsDraft.zen_channel_id ?? ''}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, zen_channel_id: e.target.value }))}
                      />
                    </div>
                  </div>
                </section>

                <section className="ap-section">
                  <h3>Контент и правило 60/40</h3>
                  <div className="management-form-row">
                    <label>Процент постов с рекламой RSD AI ({apSettingsDraft.promo_ratio ?? 60}%)</label>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={5}
                      value={apSettingsDraft.promo_ratio ?? 60}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, promo_ratio: Number(e.target.value) }))}
                    />
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={apSettingsDraft.promo_ratio ?? 60}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        const safe = Number.isNaN(next) ? 60 : Math.max(0, Math.min(100, next));
                        setApSettingsDraft((p) => ({ ...p, promo_ratio: safe }));
                      }}
                    />
                    <div className="ap-ratio-labels">
                      <span>Реклама RSD AI: {apSettingsDraft.promo_ratio ?? 60}%</span>
                      <span>Нейтральные: {100 - (apSettingsDraft.promo_ratio ?? 60)}%</span>
                    </div>
                  </div>
                  <div className="management-form-row">
                    <label>Название компании</label>
                    <input
                      type="text"
                      value={apSettingsDraft.company_name ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, company_name: e.target.value }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>URL сайта</label>
                    <input
                      type="url"
                      placeholder="https://rsd.ai"
                      value={apSettingsDraft.company_url ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, company_url: e.target.value }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>Описание компании (для промо-постов)</label>
                    <textarea
                      rows={3}
                      placeholder="Кратко опишите ваш сервис..."
                      value={apSettingsDraft.company_description ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, company_description: e.target.value }))}
                    />
                  </div>
                </section>

                <section className="ap-section">
                  <h3>Темы и генерация контента</h3>
                  <div className="management-form-row">
                    <label className="management-checkbox">
                      <input
                        type="checkbox"
                        checked={apSettingsDraft.auto_topics_enabled ?? true}
                        onChange={(e) => setApSettingsDraft((p) => ({ ...p, auto_topics_enabled: e.target.checked }))}
                      />
                      Автоматическая генерация тем (веб-поиск)
                    </label>
                  </div>
                  <div className="management-form-row">
                    <label>Категории тем (через запятую)</label>
                    <input
                      type="text"
                      placeholder="ИИ, IT, Автоматизация, Нейросети"
                      value={apSettingsDraft.topic_categories ?? ''}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, topic_categories: e.target.value }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>Минимальная длина статьи (слов)</label>
                    <input
                      type="number"
                      min={100}
                      max={5000}
                      value={apSettingsDraft.article_min_words ?? 600}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, article_min_words: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="management-form-row">
                    <label>Максимальная длина статьи (слов)</label>
                    <input
                      type="number"
                      min={200}
                      max={10000}
                      value={apSettingsDraft.article_max_words ?? 1500}
                      onChange={(e) => setApSettingsDraft((p) => ({ ...p, article_max_words: Number(e.target.value) }))}
                    />
                  </div>
                </section>

                <button
                  type="submit"
                  className="btn btn-black"
                  disabled={apIsSavingSettings}
                >
                  {apIsSavingSettings ? 'Сохранение...' : 'Сохранить настройки'}
                </button>
              </form>
            )}
          </div>
        )}

        {/* TOPICS TAB */}
        {apTab === 'topics' && (
          <div className="ap-panel">
            <div className="management-content-head">
              <span>Всего тем: {apTopicsTotal}</span>
              <button
                type="button"
                className="btn btn-outline"
                disabled={apActionInProgress === 'gen-topics' || apIsLoadingTopics}
                onClick={handleApGenerateTopics}
              >
                {apActionInProgress === 'gen-topics' ? 'Генерация...' : 'Сгенерировать темы (веб)'}
              </button>
            </div>

            <form onSubmit={handleApAddTopics} className="ap-topics-form">
              <div className="management-form-row">
                <label htmlFor="ap-topics-input">Добавить темы вручную (каждая с новой строки)</label>
                <textarea
                  id="ap-topics-input"
                  rows={5}
                  placeholder={'Как ИИ меняет рынок труда\nТоп-5 нейросетей для бизнеса\n...'}
                  value={apNewTopicsText}
                  onChange={(e) => setApNewTopicsText(e.target.value)}
                />
              </div>
              <button
                type="submit"
                className="btn btn-black"
                disabled={apActionInProgress === 'add-topics' || !apNewTopicsText.trim()}
              >
                {apActionInProgress === 'add-topics' ? 'Добавление...' : 'Добавить темы'}
              </button>
            </form>

            {apIsLoadingTopics ? (
              <p>Загрузка тем...</p>
            ) : (
              <div className="management-table-wrap">
                <table className="management-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Тема</th>
                      <th>Источник</th>
                      <th>Статус</th>
                      <th>Дата</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {apTopics.map((t) => (
                      <tr key={t.id} className={t.used ? 'ap-row-used' : ''}>
                        <td>{t.id}</td>
                        <td>{t.topic}</td>
                        <td>{t.source === 'auto' ? 'Авто' : 'Ручная'}</td>
                        <td>{t.used ? 'Использована' : 'Свободна'}</td>
                        <td>{t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            disabled={apActionInProgress === `del-topic-${t.id}`}
                            onClick={() => handleApDeleteTopic(t.id)}
                          >
                            {apActionInProgress === `del-topic-${t.id}` ? '...' : 'Удалить'}
                          </button>
                        </td>
                      </tr>
                    ))}
                    {apTopics.length === 0 && (
                      <tr><td colSpan={6}>Тем пока нет. Добавьте вручную или сгенерируйте.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* IMAGES TAB */}
        {apTab === 'images' && (
          <div className="ap-panel">
            <div className="management-content-head">
              <span>Изображений: {apImages.length}</span>
              <label className="btn btn-black ap-upload-btn" htmlFor="ap-image-upload">
                {apActionInProgress === 'upload-images' ? 'Загрузка...' : '+ Загрузить'}
                <input
                  id="ap-image-upload"
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  style={{ display: 'none' }}
                  onChange={handleApUploadImages}
                  disabled={apActionInProgress === 'upload-images'}
                />
              </label>
            </div>

            {apIsLoadingImages ? (
              <p>Загрузка изображений...</p>
            ) : (
              <div className="ap-images-grid">
                {apImages.map((img) => (
                  <div key={img.id} className="ap-image-card">
                    <img
                      src={`${ENV_CONFIG.API.BASE_URL}${img.url}`}
                      alt={img.original_name}
                      className="ap-image-thumb"
                      loading="lazy"
                    />
                    <div className="ap-image-info">
                      <span className="ap-image-name" title={img.original_name}>
                        {img.original_name.length > 20
                          ? `${img.original_name.slice(0, 18)}…`
                          : img.original_name}
                      </span>
                      <span className="ap-image-size">
                        {img.size_bytes > 1024 * 1024
                          ? `${(img.size_bytes / 1024 / 1024).toFixed(1)} МБ`
                          : `${(img.size_bytes / 1024).toFixed(0)} КБ`}
                      </span>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        disabled={apActionInProgress === `del-img-${img.id}`}
                        onClick={() => handleApDeleteImage(img.id)}
                      >
                        {apActionInProgress === `del-img-${img.id}` ? '...' : 'Удалить'}
                      </button>
                    </div>
                  </div>
                ))}
                {apImages.length === 0 && (
                  <p>Изображений нет. Загрузите PNG/JPG/WEBP для вставки в статьи.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* JOBS TAB */}
        {apTab === 'jobs' && (
          <div className="ap-panel">
            <div className="management-content-head">
              <span>Всего задач: {apJobsTotal}</span>
              <button
                type="button"
                className="btn btn-outline"
                disabled={apIsLoadingJobs}
                onClick={async () => {
                  try {
                    setApIsLoadingJobs(true);
                    const data = await adminService.apGetJobs(adminToken);
                    setApJobs(data.items ?? []);
                    setApJobsTotal(data.total ?? 0);
                  } catch (err) {
                    setApError(formatError(err));
                  } finally {
                    setApIsLoadingJobs(false);
                  }
                }}
              >
                Обновить
              </button>
            </div>
            {apIsLoadingJobs ? (
              <p>Загрузка истории...</p>
            ) : (
              <div className="management-table-wrap">
                <table className="management-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Статус</th>
                      <th>Платформа</th>
                      <th>Тема</th>
                      <th>Тип</th>
                      <th>Дата</th>
                      <th>Ссылка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apJobs.map((job) => (
                      <tr key={job.id}>
                        <td>{job.id}</td>
                        <td>
                          <span className={`management-badge ${statusClass(job.status)}`}>
                            {statusLabel(job.status)}
                          </span>
                        </td>
                        <td>{job.platform === 'vcru' ? 'vc.ru' : 'Яндекс Дзен'}</td>
                        <td title={job.topic}>
                          {job.topic.length > 50 ? `${job.topic.slice(0, 48)}…` : job.topic}
                        </td>
                        <td>
                          <span className={job.is_promo ? 'ap-badge-promo' : 'ap-badge-neutral'}>
                            {job.is_promo ? 'Промо' : 'Нейтральный'}
                          </span>
                        </td>
                        <td>
                          {job.created_at
                            ? new Date(job.created_at).toLocaleString('ru-RU')
                            : '-'}
                        </td>
                        <td>
                          {job.published_url ? (
                            <a href={job.published_url} target="_blank" rel="noopener noreferrer">
                              Открыть
                            </a>
                          ) : job.last_error ? (
                            <span className="ap-error-hint" title={job.last_error}>Ошибка</span>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                    {apJobs.length === 0 && (
                      <tr><td colSpan={7}>Задач пока нет</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* RUN / PREVIEW TAB */}
        {apTab === 'run' && (
          <div className="ap-panel">
            <section className="ap-section">
              <h3>Запустить публикацию сейчас</h3>
              <form onSubmit={handleApRunNow} className="ap-run-form">
                <div className="management-form-row">
                  <label>Платформа</label>
                  <select
                    value={apRunNowPlatform}
                    onChange={(e) => setApRunNowPlatform(e.target.value)}
                  >
                    <option value="">Авто (по настройкам)</option>
                    <option value="vcru">vc.ru</option>
                    <option value="yandex_zen">Яндекс Дзен</option>
                  </select>
                </div>
                <div className="management-form-row">
                  <label>Тема (необязательно)</label>
                  <input
                    type="text"
                    placeholder="Оставьте пустым для автовыбора из пула"
                    value={apRunNowTopic}
                    onChange={(e) => setApRunNowTopic(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-black"
                  disabled={apActionInProgress === 'run-now'}
                >
                  {apActionInProgress === 'run-now' ? 'Запуск...' : 'Опубликовать сейчас'}
                </button>
              </form>
            </section>

            <section className="ap-section">
              <h3>Предпросмотр статьи</h3>
              <form onSubmit={handleApPreview} className="ap-run-form">
                <div className="management-form-row">
                  <label>Тема статьи</label>
                  <input
                    type="text"
                    placeholder="Например: Как автоматизировать бизнес с помощью ИИ"
                    value={apPreviewTopic}
                    onChange={(e) => setApPreviewTopic(e.target.value)}
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-outline"
                  disabled={apActionInProgress === 'preview' || !apPreviewTopic.trim()}
                >
                  {apActionInProgress === 'preview' ? 'Генерация...' : 'Сгенерировать предпросмотр'}
                </button>
              </form>

              {apPreviewResult && (
                <div className="ap-preview-result">
                  <div className="ap-preview-header">
                    <strong>Заголовок:</strong> {apPreviewResult.title}
                    <span className={apPreviewResult.is_promo ? 'ap-badge-promo' : 'ap-badge-neutral'}>
                      {apPreviewResult.is_promo ? 'Промо' : 'Нейтральный'}
                    </span>
                  </div>
                  <div
                    className="ap-preview-content"
                    dangerouslySetInnerHTML={{ __html: apPreviewResult.content }}
                  />
                </div>
              )}
            </section>
          </div>
        )}
      </>
    );
  };

  const renderEmailBroadcast = () => (
    <>
      <div className="management-content-head">
        <h2>Email рассылка</h2>
      </div>
      {error && <div className="management-error">{error}</div>}

      <div className="management-broadcast-stack">
        <section className="management-broadcast-card">
          <h3 className="management-broadcast-card-title">Все подтверждённые пользователи</h3>
          <p className="management-broadcast-card-desc">
            Одно письмо подряд каждому пользователю с подтверждённым email в базе (без регулируемой паузы).
          </p>
          <form className="management-broadcast-form" onSubmit={handleSendEmailBroadcast}>
            <div className="management-form-row">
              <label htmlFor="broadcast-subject">Тема письма</label>
              <input
                id="broadcast-subject"
                type="text"
                maxLength={200}
                placeholder="Например: Важное обновление RSD"
                value={broadcastDraft.subject}
                onChange={(e) => setBroadcastDraft((prev) => ({ ...prev, subject: e.target.value }))}
              />
            </div>

            <div className="management-form-row">
              <label htmlFor="broadcast-body">Текст письма</label>
              <textarea
                id="broadcast-body"
                rows={10}
                maxLength={15000}
                placeholder="Введите текст рассылки. HTML-оформление будет применено автоматически."
                value={broadcastDraft.body}
                onChange={(e) => setBroadcastDraft((prev) => ({ ...prev, body: e.target.value }))}
              />
            </div>

            <div className="management-broadcast-actions">
              <button
                type="submit"
                className="btn btn-black"
                disabled={actionInProgress === 'email-broadcast' || actionInProgress === 'email-targeted'}
              >
                {actionInProgress === 'email-broadcast' ? 'Отправка...' : 'Запустить рассылку'}
              </button>
            </div>
          </form>
          {broadcastResult && (
            <div className="management-broadcast-result">
              <strong>Результат:</strong>
              <span> всего: {broadcastResult.total_recipients ?? 0}</span>
              <span> отправлено: {broadcastResult.sent ?? 0}</span>
              <span> ошибок: {broadcastResult.failed ?? 0}</span>
            </div>
          )}
        </section>

        <section className="management-broadcast-card management-targeted-card">
          <h3 className="management-broadcast-card-title">Точечная рассылка по группам</h3>
          <p className="management-broadcast-card-desc">
            Создайте группы и вставьте списки email (через запятую, с новой строки, из Excel). Адреса будут
            извлечены и приведены к одному формату. Отправка через API MailoPost (
            <a href="https://mailopost.ru/api.html" target="_blank" rel="noreferrer">
              документация
            </a>
            ) — по одному письму с настраиваемой паузой, чтобы снизить риск лимитов.
          </p>

          <form className="management-targeted-groups" onSubmit={(e) => e.preventDefault()}>
            {targetedGroups.map((g) => (
              <div key={g.id} className="management-targeted-group-row">
                <label className="management-targeted-group-check">
                  <input
                    type="checkbox"
                    checked={g.selected}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setTargetedGroups((prev) =>
                        prev.map((row) => (row.id === g.id ? { ...row, selected: checked } : row))
                      );
                    }}
                  />
                  <span>Включить в рассылку</span>
                </label>
                <div className="management-form-row">
                  <label>Название группы</label>
                  <input
                    type="text"
                    maxLength={120}
                    value={g.title}
                    onChange={(e) => {
                      const v = e.target.value;
                      setTargetedGroups((prev) =>
                        prev.map((row) => (row.id === g.id ? { ...row, title: v } : row))
                      );
                    }}
                    placeholder="Например: Партнёры Q2"
                  />
                </div>
                <div className="management-form-row">
                  <label>Список email</label>
                  <textarea
                    rows={5}
                    className="management-targeted-emails-input"
                    value={g.emailsRaw}
                    onChange={(e) => {
                      const v = e.target.value;
                      setTargetedGroups((prev) =>
                        prev.map((row) => (row.id === g.id ? { ...row, emailsRaw: v } : row))
                      );
                    }}
                    placeholder={'Один адрес на строку или через запятую:\nuser@mail.ru, other@company.org'}
                  />
                </div>
                {targetedGroups.length > 1 && (
                  <button
                    type="button"
                    className="btn btn-outline management-targeted-remove"
                    onClick={() => removeTargetedGroup(g.id)}
                  >
                    Удалить группу
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="btn btn-outline" onClick={addTargetedGroup}>
              + Добавить группу
            </button>
          </form>

          <form className="management-broadcast-form management-targeted-message" onSubmit={handleTargetedSend}>
            <div className="management-form-row">
              <label>Пауза между письмами (секунд)</label>
              <input
                type="number"
                min={30}
                max={86400}
                step={1}
                value={targetedIntervalSeconds}
                onChange={(e) => setTargetedIntervalSeconds(Number(e.target.value))}
              />
              <span className="management-broadcast-hint">
                По умолчанию 900 с (15 мин). Минимум 30 с, максимум сутки.
              </span>
            </div>
            <div className="management-form-row">
              <label htmlFor="targeted-subject">Тема письма</label>
              <input
                id="targeted-subject"
                type="text"
                maxLength={200}
                value={targetedBroadcastDraft.subject}
                onChange={(e) =>
                  setTargetedBroadcastDraft((prev) => ({ ...prev, subject: e.target.value }))
                }
              />
            </div>
            <div className="management-form-row">
              <label htmlFor="targeted-body">Текст письма</label>
              <textarea
                id="targeted-body"
                rows={8}
                maxLength={15000}
                value={targetedBroadcastDraft.body}
                onChange={(e) =>
                  setTargetedBroadcastDraft((prev) => ({ ...prev, body: e.target.value }))
                }
                placeholder="Текст точечной рассылки (как для общей рассылки — простой текст, оформление в письме)."
              />
            </div>
            <div className="management-broadcast-actions management-targeted-actions">
              <button
                type="button"
                className="btn btn-outline"
                disabled={targetedPreviewLoading || actionInProgress === 'email-targeted'}
                onClick={handleTargetedPreview}
              >
                {targetedPreviewLoading ? 'Разбор списков...' : 'Проверить списки'}
              </button>
              <button
                type="submit"
                className="btn btn-black"
                disabled={actionInProgress === 'email-targeted' || actionInProgress === 'email-broadcast'}
              >
                {actionInProgress === 'email-targeted' ? 'Постановка в очередь...' : 'Запустить точечную рассылку'}
              </button>
            </div>
          </form>

          {targetedPreview && (
            <div className="management-targeted-preview">
              <strong>Разбор адресов:</strong>
              <span> уникальных получателей: {targetedPreview.unique_total ?? 0}</span>
              {targetedPreview.recipient_preview?.length > 0 && (
                <div className="management-targeted-preview-emails">
                  Примеры: {targetedPreview.recipient_preview.join(', ')}
                  {(targetedPreview.unique_total || 0) > targetedPreview.recipient_preview.length ? '…' : ''}
                </div>
              )}
              {targetedPreview.per_group && (
                <ul className="management-targeted-per-group">
                  {Object.entries(targetedPreview.per_group).map(([title, info]) => (
                    <li key={title}>
                      <strong>{title}</strong>: в группе {info.parsed_in_group}, в кампанию добавлено{' '}
                      {info.new_unique_for_campaign}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {targetedJobStatus && (
            <div
              className={`management-broadcast-result management-targeted-job ${
                targetedJobStatus.status === 'failed' ? 'is-error' : ''
              }`}
            >
              <strong>Статус точечной рассылки:</strong>
              <span>{targetedJobStatus.status}</span>
              <span>
                {targetedJobStatus.sent ?? 0} / {targetedJobStatus.total ?? 0} отправлено
              </span>
              <span>ошибок: {targetedJobStatus.failed ?? 0}</span>
              {targetedJobStatus.status === 'running' && targetedJobStatus.last_recipient && (
                <span className="management-cell-muted">текущий: {targetedJobStatus.last_recipient}</span>
              )}
              {targetedJobStatus.error && (
                <span className="management-targeted-job-error">{targetedJobStatus.error}</span>
              )}
            </div>
          )}
        </section>
      </div>
    </>
  );

  return (
    <div className="management-page">
      <header className="management-header">
        <h1>Админ-панель</h1>
      </header>

      {!adminToken ? (
        <main className="management-login-wrap">
          <form className="management-login-card" onSubmit={handleLogin}>
            <h2>Вход для администратора</h2>

            <label htmlFor="admin-login">Логин</label>
            <input
              id="admin-login"
              type="text"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              autoComplete="username"
              disabled={isSubmitting}
            />

            <label htmlFor="admin-password">Пароль</label>
            <input
              id="admin-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={isSubmitting}
            />

            {error && <div className="management-error">{error}</div>}

            <button type="submit" className="btn btn-black management-login-btn" disabled={isSubmitting}>
              {isSubmitting ? 'Проверка...' : 'Войти'}
            </button>
          </form>
        </main>
      ) : (
        <main className="management-dashboard">
          <aside className="management-sidebar">
            <h3>Меню</h3>
            <nav>
              {MENU_ITEMS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`management-menu-item ${activeSection === item.id ? 'active' : ''}`}
                  onClick={() => setActiveSection(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            <button type="button" className="btn btn-outline management-logout" onClick={handleLogout}>
              Выйти
            </button>
          </aside>

          <section className="management-content">
            {activeSection === 'overview' && renderOverview()}
            {activeSection === 'users' && renderUsers()}
            {activeSection === 'agents' && renderAgents()}
            {activeSection === 'chats' && renderChats()}
            {activeSection === 'turnkeyRequests' && renderTurnkeyRequests()}
            {activeSection === 'errorReports' && renderErrorReports()}
            {activeSection === 'billing' && renderBilling()}
            {activeSection === 'promoCodes' && renderPromoCodes()}
            {activeSection === 'emailBroadcast' && renderEmailBroadcast()}
            {activeSection === 'contentPublisher' && renderContentPublisher()}
          </section>
        </main>
      )}
    </div>
  );
};

export default ManagementPortal;
