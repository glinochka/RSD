/**
 * Main Page
 * Landing page with features overview
 */

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import MainLayout from '../components/Layout';
import AgentChatShowcase from '../components/AgentChatShowcase';
import CreateChoiceModal from '../components/CreateChoiceModal';
import { NAVIGATION_ROUTES, VALIDATION } from '../config/constants';
import pricingService from '../services/pricingService';
import '../styles/main.css';

const VALUE_HIGHLIGHTS = [
  {
    id: 'time',
    title: 'Меньше рутины',
    text: 'Типовые вопросы закрывает агент — ваша команда подключается там, где нужен человек.',
  },
  {
    id: 'context',
    title: 'Ваш контекст',
    text: 'Регламенты, прайсы и инструкции остаются основой ответов: агент опирается на то, что вы ему доверили.',
  },
  {
    id: 'start',
    title: 'Быстрый старт',
    text: 'Роль, промпт, документы — и диалог в Telegram можно запускать без ожидания разработки.',
  },
];

const TESTIMONIALS = [
  {
    id: 'review-1',
    name: 'Анастасия',
    company: 'Lumi Beauty',
    segment: 'Сеть салонов красоты',
    text: 'С RSD мы закрыли большую часть типовых вопросов в Telegram. Администраторы перестали отвечать по шаблону в ручном режиме и теперь больше времени уделяют записи клиентов.',
  },
  {
    id: 'review-2',
    name: 'Руслан',
    company: 'GreenBox Logistics',
    segment: 'Логистика и доставка',
    text: 'За первую неделю запустили агента для входящих обращений от партнеров. Сократилось количество эскалаций, а ответы по SLA стали заметно стабильнее.',
  },
  {
    id: 'review-3',
    name: 'Марина',
    company: 'Focus Learning',
    segment: 'Онлайн-образование',
    text: 'Мы загрузили базу материалов и регламенты, и агент начал помогать ученикам 24/7. Команда поддержки обрабатывает сложные кейсы, а не повторяющиеся вопросы.',
  },
  {
    id: 'review-4',
    name: 'Илья',
    company: 'TechNova',
    segment: 'B2B SaaS, продажи',
    text: 'Агент берет первый контакт и квалификацию заявок. Менеджеры получают уже подготовленные диалоги и быстрее доводят клиентов до демо.',
  },
];

const CASE_STUDIES = [
  {
    id: 'case-beauty',
    title: 'Сеть салонов красоты: единая линия записи в Telegram',
    client: 'Be love',
    segment: 'Сеть салонов красоты · 7 филиалов',
    duration: 'Пилот — 3 дня, полный запуск — 8 дней',
    challenge:
      'Администраторы в разных филиалах отвечали на одни и те же вопросы о ценах, мастерах и свободных слотах. В пиковые часы очередь в чате доходила до 40–50 минут, а часть обращений терялась из‑за переключения между мессенджерами.',
    solution:
      'Собрали агента на базе прайса, расписания мастеров и регламента записи. Настроили сценарии: подбор услуги, уточнение филиала, предложение ближайших слотов и передача сложных кейсов (перенос, жалоба) живому администратору с готовой сводкой диалога.',
    results: [
      'До 72% входящих в Telegram закрывается без участия администратора.',
      'Среднее время первого ответа сократилось с 38 до 5 минут.',
      'Загрузка администраторов в вечерние смены снизилась на 42%.',
    ],
    highlight: { value: '−87%', label: 'время первого ответа' },
  },
  {
    id: 'case-logistics',
    title: 'Логистика: статусы отправлений и SLA для партнёров',
    client: 'Феникс Логистик',
    segment: 'B2B-доставка · 120+ корпоративных клиентов',
    duration: 'Запуск пилота — 2 рабочих дня',
    challenge:
      'Менеджеры по работе с партнёрами тратили до 4 часов в день на однотипные запросы: где груз, почему задержка, как оформить возврат. Ответы разъезжались по шаблонам в личных чатах, из‑за чего SLA по критичным обращениям «плавал».',
    solution:
      'Подключили агента к базе статусов и внутренним инструкциям по эскалации. Агент уточняет номер накладной, возвращает актуальный статус из регламента и при отклонении от нормы создаёт структурированную заявку менеджеру с контекстом переписки.',
    results: [
      'До 63% обращений партнёров решаются без эскалации на менеджера.',
      'Доля просрочек по SLA на первой линии снизилась на 38% уже в первые две недели.',
      'Команда из 6 менеджеров высвободила до 18 часов в неделю на онбординг новых клиентов.',
    ],
    highlight: { value: '−38%', label: 'просрочки по SLA' },
  },
  {
    id: 'case-education',
    title: 'Подготовка к ЕГЭ: поддержка учеников и кураторов 24/7',
    client: 'ЕГЭЛЕНД',
    segment: 'Онлайн-школа · 3 200 активных учеников',
    duration: 'От прототипа до продакшена — 5 дней',
    challenge:
      'Поддержка не успевала закрывать повторяющиеся вопросы о доступах, дедлайнах и материалах курса. Ночные и выходные обращения копились до понедельника, а кураторы отвлекались от проверки домашних заданий.',
    solution:
      'Загрузили базу курсов, FAQ и регламенты кураторов. Агент отвечает по материалам уроков, подсказывает шаги восстановления доступа и маршрутизирует нестандартные запросы (возврат, смена тарифа) в отдельный поток с тегами для команды.',
    results: [
      'Ночные и выходные обращения закрываются в течение минут, а не «до понедельника».',
      'До 76% типовых вопросов учеников обрабатываются без участия куратора.',
      'Команда из 8 кураторов экономит до 14 часов в неделю на рутинных ответах.',
    ],
    highlight: { value: '76%', label: 'вопросов без куратора' },
  },
  {
    id: 'case-saas',
    title: 'B2B SaaS: квалификация лидов и подготовка к демо',
    client: 'TechNova',
    segment: 'B2B SaaS · отдел продаж 14 менеджеров',
    duration: 'Настройка и A/B — 7 дней',
    challenge:
      'Входящие заявки с сайта и мессенджеров приходили с неполным контекстом: менеджеры тратили 15–20 минут на уточнение размера команды, сценария использования и сроков внедрения. Часть «тёплых» лидов остывала до первого звонка.',
    solution:
      'Настроили агента с ветками квалификации по ICP, сбором обязательных полей и правилами передачи в CRM. Перед передачей менеджеру агент формирует карточку лида: сегмент, боль, бюджетный ориентир и удобное время для демо.',
    results: [
      'Среднее время подготовки лида к звонку сократилось с 18 до 4 минут.',
      'Конверсия из первого контакта в назначенное демо выросла на 31% за месяц пилота.',
      'В 2,5 раза больше диалогов передаётся менеджеру с полным контекстом и готовой карточкой.',
    ],
    highlight: { value: '+31%', label: 'конверсия в демо' },
  },
];

const IMPACT_METRICS = [
  {
    id: 'requests',
    value: 'до 68%',
    label: 'типовых запросов автоматизируется',
  },
  {
    id: 'launch',
    value: '1-2 дня',
    label: 'на запуск пилотного агента',
  },
  {
    id: 'channels',
    value: '3 канала',
    label: 'поддержки чаще всего закрывают одним сценарием',
  },
  {
    id: 'team',
    value: 'x2',
    label: 'быстрее подключаются новые сотрудники',
  },
];

const BUSINESS_SCENARIOS = [
  {
    id: 'support',
    label: 'Поддержка',
    title: 'Снижайте нагрузку на первую линию',
    challenge:
      'Повторяющиеся вопросы о статусах, графике и условиях забирают время команды и растягивают очередь в чате.',
    outcome:
      'Агент берёт типовые обращения 24/7, а сотрудники подключаются только к нестандартным и конфликтным кейсам.',
    firstStep: 'Соберите 10-15 частых вопросов из чатов и добавьте короткие эталонные ответы.',
  },
  {
    id: 'sales',
    label: 'Продажи',
    title: 'Квалифицируйте входящие заявки быстрее',
    challenge:
      'Менеджеры тратят много времени на первичный контакт и одинаковые уточнения, из-за чего теряются теплые лиды.',
    outcome:
      'Агент уточняет ключевые параметры запроса и передает менеджеру уже подготовленный диалог с контекстом.',
    firstStep: 'Опишите критерии квалификации лида и 3-5 веток первого диалога.',
  },
  {
    id: 'onboarding',
    label: 'Онбординг',
    title: 'Ускоряйте обучение новых сотрудников',
    challenge:
      'Новички долго ищут ответы в регламентах и отвлекают наставников от работы с клиентами.',
    outcome:
      'Агент помогает быстро находить правила и подсказывает шаги по процессу прямо в рабочем чате.',
    firstStep: 'Загрузите регламенты, FAQ и выделите разделы, которые чаще всего вызывают ошибки.',
  },
];

const LAUNCH_STEPS = [
  'Определяете роль агента и собираете 10-15 частых вопросов.',
  'Добавляете базу знаний: документы, правила, тон коммуникации.',
  'Тестируете сценарии на реальных диалогах и уточняете ответы.',
  'Запускаете в рабочем канале и отслеживаете метрики качества.',
];

const FLOATING_PHRASES = [
  'Интеграция с CRM',
  'Запуск за 5 минут',
  'Быстрое подключение',
  'Множество каналов',
  'Единый дашборд',
  'Без кода',
  'Telegram и мессенджеры',
  'База знаний компании',
  'Автоответы 24/7',
  'Поддержка и продажи',
  'Контроль качества',
  'Гибкие сценарии',
  'Командная работа',
  'Быстрый онбординг',
  'Аналитика диалогов',
  'Омниканальная поддержка',
  'AI-ассистент для команды',
  'Шаблоны ответов',
  'Сценарии под ваш бизнес',
  'Автоматизация рутины',
  'История диалогов',
  'Прозрачные метрики',
  'Подключение базы FAQ',
  'Готовые роли агента',
  'Контроль тональности',
  'Экономия времени команды',
  'Гибкие настройки',
  'Скорость внедрения',
  'Подключение без кода',
  'Точнее ответы',
  'Масштабирование поддержки',
  'Подключение WhatsApp',
  'Подключение Telegram',
  'Подключение сайта',
  'Единая база знаний',
  'Ответы по вашим документам',
  'Обучение на ваших материалах',
  'Понятные сценарии диалога',
  'Быстрый старт команды',
  'Меньше ручной рутины',
  'Экономия на первой линии',
  'Снижение времени ответа',
  'Быстрая обработка заявок',
  'Квалификация лидов',
  'Автоответы клиентам 24/7',
  'Подсказки для менеджеров',
  'Стандарты общения',
  'Единый стиль ответов',
  'Контроль ошибок в ответах',
  'Готовые бизнес-шаблоны',
  'Гибкие роли ассистента',
  'Удобная панель управления',
  'Сводка по диалогам',
  'Отчеты по качеству',
  'Контроль SLA',
  'Быстрое внедрение в отдел',
  'Помощь новым сотрудникам',
  'Сокращение нагрузки на поддержку',
  'Запуск без технической команды',
  'Простая настройка сценариев',
  'Без долгой интеграции',
  'Поддержка клиентов в одном окне',
  'Автоматизация повторяющихся вопросов',
  'Ускорение продаж в чате',
  'Поддержка внутренних процессов',
  'Масштабирование без найма',
  'Прозрачные результаты внедрения',
  'Улучшение клиентского опыта',
  'Быстрое подключение каналов',
  'Актуальные ответы по базе',
  'Точки роста в аналитике',
  'Гибкие правила маршрутизации',
  'Плавный запуск пилота',
  'Управление знаниями команды',
  'Единый входящий поток',
  'Снижение стоимости обращения',
  'Контроль контекста ответа',
  'Быстрый запуск без кода',
  'Повышение конверсии обращений',
  'Качественный сервис 24/7',
  'Подключение по API',
];

const FLOATING_LANES = [10, 18, 26, 34, 42, 50, 58, 66, 74, 82, 90];
const FLOATING_SIZES = ['sm', 'md', 'lg'];
const FLOATING_MIN_DURATION_SECONDS = 28;
const FLOATING_MAX_DURATION_SECONDS = 34;
const FLOATING_SPAWN_INTERVAL_MS = 340;
const FLOATING_INITIAL_BURST_COUNT = 18;
const FLOATING_MIN_GAP_MS_SAME_LANE = 6000;
const FLOATING_VERTICAL_JITTER_PX = 3;
const FLOATING_LANE_DIRECTIONS = FLOATING_LANES.reduce((acc, lane, index) => {
  acc[lane] = index % 2 === 0 ? 'left' : 'right';
  return acc;
}, {});

const FAQ_ITEMS = [
  {
    id: 'faq-1',
    question: 'Нужны ли разработчики, чтобы запустить агента?',
    answer:
      'Нет. Вы задаёте роль, промпт и прикрепляете документы — агент готов к диалогу в Telegram. Доработки и уточнения сценария можно делать самостоятельно, без кода.',
  },
  {
    id: 'faq-2',
    question: 'На чём основываются ответы агента?',
    answer:
      'Агент опирается на загруженные вами материалы и инструкции. Вы контролируете тон и границы тем: типовые вопросы закрывает агент, сложные случаи остаются за людьми.',
  },
  {
    id: 'faq-3',
    question: 'Можно ли использовать корпоративные документы?',
    answer:
      'Платформа рассчитана на рабочий контекст: регламенты, прайсы, FAQ. Обращайте внимание на политику обработки данных в вашей организации и настройки доступа к боту.',
  },
  {
    id: 'faq-4',
    question: 'Сколько времени занимает первый запуск?',
    answer:
      'Часто достаточно от нескольких часов до пары дней: зависит от объёма базы знаний и того, насколько детально вы хотите прогнать тестовые диалоги перед включением для клиентов.',
  },
  {
    id: 'faq-5',
    question: 'Как контролировать качество ответов после запуска?',
    answer:
      'Используйте тестовые диалоги и регулярно просматривайте реальные переписки: отмечайте неточные ответы, обновляйте базу знаний и корректируйте промпт. Лучше делать короткие итерации каждую неделю, чем редкие большие изменения.',
  },
];

const getInitials = (name) => {
  const trimmed = name.trim();
  if (!trimmed) return '?';
  const parts = trimmed.replace(/,/g, ' ').split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  const word = parts[0];
  if (word.length >= 2) return `${word[0]}${word[1]}`.toUpperCase();
  return word[0].toUpperCase();
};

const Main = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [activeTestimonialIndex, setActiveTestimonialIndex] = useState(0);
  const [activeCaseIndex, setActiveCaseIndex] = useState(0);
  const [activeScenarioId, setActiveScenarioId] = useState(BUSINESS_SCENARIOS[0].id);
  const [openFaqId, setOpenFaqId] = useState(null);
  const [isSubmittingTurnkeyRequest, setIsSubmittingTurnkeyRequest] = useState(false);
  const [floatingPhrases, setFloatingPhrases] = useState([]);
  const [turnkeyRequestForm, setTurnkeyRequestForm] = useState({
    phoneNumber: '',
    email: '',
    employeeRequest: '',
  });
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const mainContentRef = useRef(null);
  const floatingPhraseTimeoutsRef = useRef(new Set());
  const floatingLaneReleaseTimeoutsRef = useRef(new Set());
  const floatingSpawnTimeoutsRef = useRef(new Set());
  const floatingLaneLastSpawnRef = useRef(new Map());
  const floatingLaneOccupiedRef = useRef(new Set());

  useEffect(() => {
    const root = mainContentRef.current;
    if (!root) return undefined;

    const revealItems = root.querySelectorAll('.reveal-on-scroll');
    if (!revealItems.length) return undefined;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isMobileViewport = window.matchMedia('(max-width: 768px)').matches;
    if (prefersReducedMotion || isMobileViewport) {
      revealItems.forEach((item) => item.classList.add('is-visible'));
      return undefined;
    }

    if (!('IntersectionObserver' in window)) {
      revealItems.forEach((item) => item.classList.add('is-visible'));
      return undefined;
    }

    root.classList.add('reveal-ready');

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      },
      {
        threshold: 0.16,
        rootMargin: '0px 0px -10% 0px',
      }
    );

    revealItems.forEach((item) => observer.observe(item));

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const spawnPhrase = () => {
      const now = Date.now();
      const availableLanes = FLOATING_LANES.filter(
        (laneValue) =>
          !floatingLaneOccupiedRef.current.has(laneValue) &&
          now - (floatingLaneLastSpawnRef.current.get(laneValue) || 0) >= FLOATING_MIN_GAP_MS_SAME_LANE
      );
      if (!availableLanes.length) return;
      const lanePool = availableLanes;
      const lane = lanePool[Math.floor(Math.random() * lanePool.length)];
      const text = FLOATING_PHRASES[Math.floor(Math.random() * FLOATING_PHRASES.length)];
      const direction = FLOATING_LANE_DIRECTIONS[lane] || 'left';
      const size = FLOATING_SIZES[Math.floor(Math.random() * FLOATING_SIZES.length)];
      const yOffset = Math.round((Math.random() * 2 - 1) * FLOATING_VERTICAL_JITTER_PX);
      const durationRange = FLOATING_MAX_DURATION_SECONDS - FLOATING_MIN_DURATION_SECONDS;
      const duration = FLOATING_MIN_DURATION_SECONDS + Math.random() * durationRange;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      floatingLaneLastSpawnRef.current.set(lane, now);
      floatingLaneOccupiedRef.current.add(lane);

      setFloatingPhrases((prev) => [
        ...prev,
        {
          id,
          text,
          lane,
          direction,
          size,
          yOffset,
          duration,
        },
      ]);

      const laneReleaseTimeoutId = window.setTimeout(() => {
        floatingLaneOccupiedRef.current.delete(lane);
        floatingLaneReleaseTimeoutsRef.current.delete(laneReleaseTimeoutId);
      }, (duration * 1000) / 2);
      floatingLaneReleaseTimeoutsRef.current.add(laneReleaseTimeoutId);

      const timeoutId = window.setTimeout(() => {
        setFloatingPhrases((prev) => prev.filter((phrase) => phrase.id !== id));
        floatingLaneOccupiedRef.current.delete(lane);
        floatingPhraseTimeoutsRef.current.delete(timeoutId);
      }, (duration + 0.4) * 1000);
      floatingPhraseTimeoutsRef.current.add(timeoutId);
    };

    for (let i = 0; i < FLOATING_INITIAL_BURST_COUNT; i += 1) {
      const startupTimeoutId = window.setTimeout(() => {
        spawnPhrase();
        floatingSpawnTimeoutsRef.current.delete(startupTimeoutId);
      }, i * 120);
      floatingSpawnTimeoutsRef.current.add(startupTimeoutId);
    }
    const intervalId = window.setInterval(spawnPhrase, FLOATING_SPAWN_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
      floatingSpawnTimeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      floatingSpawnTimeoutsRef.current.clear();
      floatingLaneReleaseTimeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      floatingLaneReleaseTimeoutsRef.current.clear();
      floatingPhraseTimeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      floatingPhraseTimeoutsRef.current.clear();
      floatingLaneLastSpawnRef.current.clear();
      floatingLaneOccupiedRef.current.clear();
    };
  }, []);

  const handleCreateClick = () => {
    if (isAuthenticated) {
      setIsCreateModalOpen(true);
    } else {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  };

  const handlePricing = () => navigate(NAVIGATION_ROUTES.PRICING);

  const handleTurnkey = () => {
    const turnkeySection = document.getElementById('turnkey');
    if (turnkeySection) {
      turnkeySection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    navigate(NAVIGATION_ROUTES.PRICING);
  };
  const handleNextTestimonial = () =>
    setActiveTestimonialIndex((prev) => (prev + 1) % TESTIMONIALS.length);
  const handlePrevTestimonial = () =>
    setActiveTestimonialIndex((prev) => (prev - 1 + TESTIMONIALS.length) % TESTIMONIALS.length);
  const handleNextCase = () => setActiveCaseIndex((prev) => (prev + 1) % CASE_STUDIES.length);
  const handlePrevCase = () =>
    setActiveCaseIndex((prev) => (prev - 1 + CASE_STUDIES.length) % CASE_STUDIES.length);
  const handleSubmitTurnkeyRequest = async (event) => {
    event.preventDefault();
    if (isSubmittingTurnkeyRequest) return;

    const phoneNumber = turnkeyRequestForm.phoneNumber.trim();
    const email = turnkeyRequestForm.email.trim();
    const employeeRequest = turnkeyRequestForm.employeeRequest.trim();

    if (!phoneNumber || !email || !employeeRequest) {
      showError('Заполните все поля заявки.');
      return;
    }

    if (!VALIDATION.EMAIL_PATTERN.test(email)) {
      showError('Введите корректный email.');
      return;
    }

    try {
      setIsSubmittingTurnkeyRequest(true);
      await pricingService.createTurnkeyRequest({
        phone_number: phoneNumber,
        email,
        requested_agent: employeeRequest,
        purpose: employeeRequest,
      });
      setTurnkeyRequestForm({
        phoneNumber: '',
        email: '',
        employeeRequest: '',
      });
      showSuccess('Заявка успешно создана, мы скоро свяжемся с вами.');
    } catch (error) {
      showError(error?.response?.data?.detail || error?.message || 'Не удалось отправить заявку.');
    } finally {
      setIsSubmittingTurnkeyRequest(false);
    }
  };

  const activeTestimonial = TESTIMONIALS[activeTestimonialIndex];
  const activeCase = CASE_STUDIES[activeCaseIndex];
  const activeScenario = BUSINESS_SCENARIOS.find((scenario) => scenario.id === activeScenarioId) ?? BUSINESS_SCENARIOS[0];

  return (
    <MainLayout>
      <div className="main-content" ref={mainContentRef}>
        <section className="hero" aria-labelledby="hero-heading">
          <div className="hero-content reveal-on-scroll reveal-from-left">
            <h1 id="hero-heading">
              Портал цифровизации вашего <span className="hero-accent">бизнеса</span>
            </h1>
            <p className="description">
              RSD — no-code платформа для ИИ-агентов, сайтов и автоматизации. Создайте проект, подключите ИИ-ассистентов,
              загрузите базу знаний и запустите цифровое присутствие за минуты, не привлекая разработчиков.
            </p>
            <p className="description-lead">
              Меньше ожидания в чатах и проще онбординг — при этом вы по-прежнему контролируете, что именно говорит агент.
            </p>
            <div className="hero-actions">
              <button type="button" className="btn btn-black" onClick={handleCreateClick}>
                Создать проект
              </button>
              <button type="button" className="btn btn-outline hero-actions-secondary" onClick={handleCreateClick}>
                Создать агента
              </button>
            </div>
          </div>
          <div className="hero-media reveal-on-scroll reveal-from-right">
            <AgentChatShowcase tone="light" variant="main" />
          </div>
        </section>

        <section className="cases-section reveal-on-scroll reveal-from-bottom" aria-labelledby="cases-heading">
          <h2 id="cases-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Наши кейсы
          </h2>
          <p className="section-lead section-lead-tight reveal-on-scroll reveal-from-bottom reveal-delay-1">
            Разбор реальных внедрений: задача, решение на RSD и измеримый результат. Листайте карусель, чтобы увидеть
            разные отрасли и сценарии.
          </p>
          <div className="case-carousel reveal-on-scroll reveal-from-bottom reveal-delay-1" aria-live="polite">
            <article
              className="case-card"
              aria-label={`Кейс: ${activeCase.client}, ${activeCase.title}`}
            >
              <div key={activeCase.id} className="case-card-body">
                <header className="case-card-header">
                  <div className="case-card-header-main">
                    <p className="case-client">{activeCase.client}</p>
                    <p className="case-segment">{activeCase.segment}</p>
                    <h3 className="case-title">{activeCase.title}</h3>
                  </div>
                  <div className="case-highlight" aria-label={`Ключевой результат: ${activeCase.highlight.label}`}>
                    <p className="case-highlight-value">{activeCase.highlight.value}</p>
                    <p className="case-highlight-label">{activeCase.highlight.label}</p>
                  </div>
                </header>
                <p className="case-duration">
                  <strong>Срок внедрения:</strong> {activeCase.duration}
                </p>
                <div className="case-details">
                  <div className="case-detail-block">
                    <h4>Задача</h4>
                    <p>{activeCase.challenge}</p>
                  </div>
                  <div className="case-detail-block">
                    <h4>Решение</h4>
                    <p>{activeCase.solution}</p>
                  </div>
                  <div className="case-detail-block case-detail-block--results">
                    <h4>Результат</h4>
                    <ul className="case-results-list">
                      {activeCase.results.map((result) => (
                        <li key={result}>{result}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </article>
            <div className="case-controls">
              <button type="button" className="btn btn-outline case-nav-btn" onClick={handlePrevCase}>
                Назад
              </button>
              <div className="case-dots" role="tablist" aria-label="Кейсы">
                {CASE_STUDIES.map((item, index) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`case-dot ${index === activeCaseIndex ? 'is-active' : ''}`}
                    onClick={() => setActiveCaseIndex(index)}
                    aria-label={`Показать кейс ${index + 1}: ${item.client}`}
                    aria-selected={index === activeCaseIndex}
                    role="tab"
                  />
                ))}
              </div>
              <button type="button" className="btn btn-outline case-nav-btn" onClick={handleNextCase}>
                Далее
              </button>
            </div>
          </div>
        </section>

        <section className="value-highlights reveal-on-scroll reveal-from-bottom" aria-labelledby="value-highlights-heading">
          <h2 id="value-highlights-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Что даёт платформа на практике
          </h2>
          <p className="section-lead reveal-on-scroll reveal-from-bottom reveal-delay-1">
            Не обещаем «магии» — даём понятный инструмент: вы настраиваете роль, знания и канал общения.
          </p>
          <div className="value-highlights-grid">
            {VALUE_HIGHLIGHTS.map((block, index) => {
              const revealDirection =
                index === 0
                  ? 'reveal-from-left'
                  : index === 1
                    ? 'reveal-from-right value-highlight-card--desktop-bottom'
                    : 'reveal-from-left value-highlight-card--desktop-right';
              return (
                <article
                  key={block.id}
                  className={`value-highlight-card reveal-on-scroll ${revealDirection}`}
                >
                  <h3>{block.title}</h3>
                  <p>{block.text}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="why-rsd-section reveal-on-scroll reveal-from-bottom" aria-labelledby="why-rsd-heading">
          <h2 id="why-rsd-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Почему RSD AI?
          </h2>
          <div className="floating-phrases-shell reveal-on-scroll reveal-from-bottom reveal-delay-1" aria-hidden="true">
            {floatingPhrases.map((phrase) => (
              <span
                key={phrase.id}
                className={`floating-phrase floating-phrase--${phrase.direction} floating-phrase--${phrase.size}`}
                style={{ top: `calc(${phrase.lane}% + ${phrase.yOffset}px)`, animationDuration: `${phrase.duration}s` }}
              >
                {phrase.text}
              </span>
            ))}
          </div>
        </section>

        <section className="testimonials reveal-on-scroll reveal-from-bottom" aria-labelledby="testimonials-heading">
          <h2 id="testimonials-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Как это работает у владельцев бизнеса
          </h2>
          <p className="section-lead section-lead-tight reveal-on-scroll reveal-from-bottom reveal-delay-1">
            Ниже — примеры команд, которые уже внедрили агентов в поддержку, продажи и обучение клиентов.
          </p>
          <div className="testimonial-carousel reveal-on-scroll reveal-from-bottom reveal-delay-1" aria-live="polite">
            <article
              className="testimonial-card"
              aria-label={`Отзыв: ${activeTestimonial.name}, ${activeTestimonial.company}`}
            >
              <div key={activeTestimonial.id} className="testimonial-card-body">
                <div className="testimonial-card-top">
                  <div className="testimonial-avatar" aria-hidden="true">
                    {getInitials(activeTestimonial.name)}
                  </div>
                  <p className="testimonial-person-name">{activeTestimonial.name}</p>
                </div>
                <p className="testimonial-meta">
                  <span className="testimonial-company-part">{activeTestimonial.company}</span>
                  <span className="testimonial-meta-dot" aria-hidden="true">
                    {' '}
                    ·{' '}
                  </span>
                  <span className="testimonial-segment">{activeTestimonial.segment}</span>
                </p>
                <p className="testimonial-text">«{activeTestimonial.text}»</p>
              </div>
            </article>
            <div className="testimonial-controls">
              <button type="button" className="btn btn-outline testimonial-nav-btn" onClick={handlePrevTestimonial}>
                Назад
              </button>
              <div className="testimonial-dots" role="tablist" aria-label="Отзывы">
                {TESTIMONIALS.map((item, index) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`testimonial-dot ${index === activeTestimonialIndex ? 'is-active' : ''}`}
                    onClick={() => setActiveTestimonialIndex(index)}
                    aria-label={`Показать отзыв ${index + 1}`}
                    aria-selected={index === activeTestimonialIndex}
                    role="tab"
                  />
                ))}
              </div>
              <button type="button" className="btn btn-outline testimonial-nav-btn" onClick={handleNextTestimonial}>
                Далее
              </button>
            </div>
          </div>
        </section>

        <section className="impact-section reveal-on-scroll reveal-from-bottom" aria-labelledby="impact-heading">
          <h2 id="impact-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Что обычно меняется после внедрения
          </h2>
          <div className="impact-grid">
            {IMPACT_METRICS.map((metric) => (
              <article key={metric.id} className="impact-card reveal-on-scroll reveal-from-bottom">
                <p className="impact-value">{metric.value}</p>
                <p className="impact-label">{metric.label}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="scenarios-section reveal-on-scroll reveal-from-bottom" aria-labelledby="scenarios-heading">
          <h2 id="scenarios-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Выберите ваш сценарий внедрения
          </h2>
          <p className="section-lead section-lead-tight reveal-on-scroll reveal-from-bottom reveal-delay-1">
            Нажмите на формат, который вам ближе — увидите типичную задачу, ожидаемый результат и с чего начать в первую
            очередь.
          </p>
          <div className="scenario-tabs reveal-on-scroll reveal-from-bottom reveal-delay-1" role="tablist" aria-label="Сценарии внедрения">
            {BUSINESS_SCENARIOS.map((scenario) => {
              const isActive = scenario.id === activeScenario.id;
              return (
                <button
                  key={scenario.id}
                  type="button"
                  className={`scenario-tab ${isActive ? 'is-active' : ''}`}
                  onClick={() => setActiveScenarioId(scenario.id)}
                  role="tab"
                  aria-selected={isActive}
                  aria-controls={`scenario-panel-${scenario.id}`}
                  id={`scenario-tab-${scenario.id}`}
                >
                  {scenario.label}
                </button>
              );
            })}
          </div>
          <article
            className="scenario-card reveal-on-scroll reveal-from-bottom"
            role="tabpanel"
            id={`scenario-panel-${activeScenario.id}`}
            aria-labelledby={`scenario-tab-${activeScenario.id}`}
          >
            <h3>{activeScenario.title}</h3>
            <p>
              <strong>Типичная ситуация:</strong> {activeScenario.challenge}
            </p>
            <p>
              <strong>Что меняется:</strong> {activeScenario.outcome}
            </p>
            <p>
              <strong>Первый шаг:</strong> {activeScenario.firstStep}
            </p>
          </article>
        </section>

        <section className="launch-roadmap reveal-on-scroll reveal-from-bottom" aria-labelledby="launch-roadmap-heading">
          <h2 id="launch-roadmap-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Сценарий запуска за 4 шага
          </h2>
          <ol className="roadmap-list">
            {LAUNCH_STEPS.map((step) => (
              <li key={step} className="reveal-on-scroll reveal-from-left">
                {step}
              </li>
            ))}
          </ol>
        </section>

        <section id="turnkey" className="turnkey-section reveal-on-scroll reveal-from-bottom" aria-labelledby="turnkey-heading">
          <h2 id="turnkey-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Нужен сложный ИИ-агент под ключ?
          </h2>
          <p className="section-lead section-lead-tight reveal-on-scroll reveal-from-bottom reveal-delay-1">
            Опишете задачу - команда RSD соберет архитектуру, настроит агента под ваши процессы и поможет запустить его в
            работу без лишней рутины.
          </p>
          <form className="turnkey-request-form reveal-on-scroll reveal-from-bottom reveal-delay-1" onSubmit={handleSubmitTurnkeyRequest}>
            <label>
              Номер телефона
              <input
                type="tel"
                value={turnkeyRequestForm.phoneNumber}
                onChange={(event) => setTurnkeyRequestForm((prev) => ({ ...prev, phoneNumber: event.target.value }))}
                placeholder="+7 (900) 000-00-00"
                required
              />
            </label>
            <label>
              Электронная почта
              <input
                type="email"
                value={turnkeyRequestForm.email}
                onChange={(event) => setTurnkeyRequestForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="name@company.ru"
                required
              />
            </label>
            <label>
              Какого сотрудника вы хотите получить
              <textarea
                value={turnkeyRequestForm.employeeRequest}
                onChange={(event) => setTurnkeyRequestForm((prev) => ({ ...prev, employeeRequest: event.target.value }))}
                placeholder="Опишите роли, задачи и сценарии работы сотрудника"
                rows={4}
                required
              />
            </label>
            <button type="submit" className="btn btn-black" disabled={isSubmittingTurnkeyRequest}>
              {isSubmittingTurnkeyRequest ? 'Отправка...' : 'Отправить заявку'}
            </button>
          </form>
        </section>

        <section className="faq-section reveal-on-scroll reveal-from-bottom" aria-labelledby="faq-heading">
          <h2 id="faq-heading" className="section-title reveal-on-scroll reveal-from-bottom">
            Частые вопросы
          </h2>
          <p className="section-lead section-lead-tight reveal-on-scroll reveal-from-bottom reveal-delay-1">
            Коротко о том, как устроен старт и что вы контролируете при работе с агентом.
          </p>
          <div className="faq-list">
            {FAQ_ITEMS.map((item) => {
              const isOpen = openFaqId === item.id;
              return (
                <div key={item.id} className={`faq-item${isOpen ? ' is-open' : ''}`}>
                  <button
                    type="button"
                    className="faq-summary"
                    aria-expanded={isOpen}
                    aria-controls={`faq-panel-${item.id}`}
                    id={`faq-trigger-${item.id}`}
                    onClick={() => setOpenFaqId(isOpen ? null : item.id)}
                  >
                    {item.question}
                  </button>
                  <div
                    id={`faq-panel-${item.id}`}
                    role="region"
                    aria-labelledby={`faq-trigger-${item.id}`}
                    aria-hidden={!isOpen}
                    className="faq-answer-shell"
                  >
                    <div className="faq-answer-inner">
                      <p className="faq-answer">{item.answer}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="cta-band reveal-on-scroll reveal-from-bottom" aria-labelledby="cta-heading">
          <div className="cta-band-inner reveal-on-scroll reveal-from-bottom">
            <h2 id="cta-heading">Начните с одного агента</h2>
            <p>
              Соберите прототип за несколько минут: роль и базу знаний всегда можно уточнить позже. Если удобнее сначала
              сравнить цены на шаблоны — загляните в раздел с тарифами.
            </p>
            <div className="cta-band-actions">
              <button type="button" className="btn btn-black" onClick={handleCreateClick}>
                Создать проект
              </button>
              <button type="button" className="btn btn-outline" onClick={handlePricing}>
                Посмотреть тарифы
              </button>
            </div>
          </div>
        </section>
      </div>

      <CreateChoiceModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />
    </MainLayout>
  );
};

export default Main;