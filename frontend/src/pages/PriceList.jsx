/**
 * PriceList Page
 * Display pricing plans and features
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import MainLayout from '../components/Layout';
import { NAVIGATION_ROUTES, VALIDATION } from '../config/constants';
import pricingService from '../services/pricingService';
import {
  COMING_SOON_TEMPLATES,
  POLICY_NOTES,
  SPECIAL_CONDITIONS,
} from '../utils/agentTemplatePricing';
import { reachYandexGoal, YM_GOALS } from '../utils/yandexMetrika';
import '../styles/priceList.css';

const PENDING_YOOKASSA_PAYMENT_ID_KEY = 'pending_yookassa_payment_id';
const MARKETING_DISCOUNTS_BY_PLAN = {
  Advanced: 40,
  Pro: 60,
};
const DURATION_OPTIONS = [
  { months: 1, label: '1 месяц', discountPercent: 0 },
  { months: 3, label: '3 месяца', discountPercent: 15 },
  { months: 6, label: '6 месяцев', discountPercent: 25 },
];
const PLAN_DISPLAY_NAMES = {
  Free: 'Базовый',
  Advanced: 'Продвинутый',
  Pro: 'Про',
};

const roundUpToNextHundred = (value) => Math.ceil(value / 100) * 100;
const formatRubPrice = (value) => Number(value || 0).toLocaleString('ru-RU');
const getDurationOption = (months) => DURATION_OPTIONS.find((option) => option.months === months) || DURATION_OPTIONS[0];
const roundToPriceEndingNinety = (value) => {
  const normalized = Number(value || 0);
  if (normalized <= 0) return 0;
  return Math.max(90, Math.round((normalized - 90) / 100) * 100 + 90);
};

const calculateTotalForDuration = (monthlyPrice, months) => {
  const price = Number(monthlyPrice || 0);
  const selectedOption = getDurationOption(months);
  const baseTotal = price * selectedOption.months;
  const discountedTotal = Math.round(baseTotal * (1 - selectedOption.discountPercent / 100));
  return roundToPriceEndingNinety(discountedTotal);
};

const PriceList = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError, showInfo, showSuccess } = useNotification();
  const [plans, setPlans] = useState([]);
  const [agentTemplates, setAgentTemplates] = useState([]);
  const [policyNotes, setPolicyNotes] = useState(POLICY_NOTES);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
  const [requestModalConfig, setRequestModalConfig] = useState({
    title: 'Заявка на тариф «Агент под ключ»',
    requestPlaceholder: 'Опишите роли, задачи и сценарии работы сотрудника',
    defaultAgentLabel: '',
  });
  const [isSubmittingRequest, setIsSubmittingRequest] = useState(false);
  const [isPurchaseModalOpen, setIsPurchaseModalOpen] = useState(false);
  const [selectedPaidPlan, setSelectedPaidPlan] = useState(null);
  const [selectedDurationMonths, setSelectedDurationMonths] = useState(1);
  const [purchasePromoCode, setPurchasePromoCode] = useState('');
  const [requestForm, setRequestForm] = useState({
    phoneNumber: '',
    email: '',
    employeeRequest: '',
  });

  const resetRequestForm = () => {
    setRequestForm({
      phoneNumber: '',
      email: '',
      employeeRequest: '',
    });
  };

  const handleOpenSpecialRequest = (offer) => {
    setRequestModalConfig({
      title: offer.modalTitle,
      requestPlaceholder: offer.requestPlaceholder,
      defaultAgentLabel: offer.requestLabel,
    });
    setRequestForm((prev) => ({
      ...prev,
      employeeRequest: offer.requestLabel,
    }));
    setIsRequestModalOpen(true);
  };

  const handleCloseRequestModal = () => {
    if (isSubmittingRequest) return;
    setIsRequestModalOpen(false);
    resetRequestForm();
  };

  const handleClosePurchaseModal = () => {
    if (isProcessingPayment) return;
    setIsPurchaseModalOpen(false);
    setSelectedPaidPlan(null);
    setSelectedDurationMonths(1);
    setPurchasePromoCode('');
  };

  const handleSelectPlan = async (plan) => {
    if (!plan) return;
    if (plan.disabled) {
      showInfo('Этот шаблон пока недоступен.');
      return;
    }
    if (plan.requestOnly) {
      setRequestModalConfig({
        title: 'Заявка на тариф «Агент под ключ»',
        requestPlaceholder: 'Опишите роли, задачи и сценарии работы сотрудника',
        defaultAgentLabel: 'Агент под ключ',
      });
      setIsRequestModalOpen(true);
      return;
    }

    navigate(isAuthenticated ? NAVIGATION_ROUTES.CREATE_AGENT : NAVIGATION_ROUTES.AUTH);
  };

  const handleSubmitPurchase = async () => {
    if (!selectedPaidPlan) {
      showError('Не удалось найти выбранный тариф.');
      return;
    }

    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
      return;
    }

    if (!selectedPaidPlan.is_paid) {
      navigate(NAVIGATION_ROUTES.CREATE_AGENT);
      return;
    }

    if (isProcessingPayment) return;
    setIsProcessingPayment(true);
    try {
      const returnUrl = `${window.location.origin}${NAVIGATION_ROUTES.PRICING}`;
      const payment = await pricingService.createYooKassaPayment({
        plan_name: selectedPaidPlan.code,
        return_url: returnUrl,
        promo_code: purchasePromoCode.trim() || undefined,
        duration_months: selectedDurationMonths,
      });

      if (payment?.status === 'succeeded' && !payment?.confirmation_url) {
        reachYandexGoal(YM_GOALS.TARIFF_PURCHASE_SUCCESS);
        showSuccess('Подписка активирована по промокоду.');
        handleClosePurchaseModal();
        setIsProcessingPayment(false);
        return;
      }

      if (!payment?.confirmation_url || !payment?.payment_id) {
        throw new Error('Сервис оплаты вернул некорректный ответ.');
      }

      localStorage.setItem(PENDING_YOOKASSA_PAYMENT_ID_KEY, payment.payment_id);
      window.location.href = payment.confirmation_url;
    } catch (error) {
      showError(error?.message || 'Не удалось создать платеж. Попробуйте еще раз.');
      setIsProcessingPayment(false);
    }
  };

  const handleSubmitTurnkeyRequest = async (event) => {
    event.preventDefault();
    if (isSubmittingRequest) return;

    const phoneNumber = requestForm.phoneNumber.trim();
    const email = requestForm.email.trim();
    const employeeRequest = requestForm.employeeRequest.trim();

    if (!phoneNumber || !email || !employeeRequest) {
      showError('Заполните все поля заявки.');
      return;
    }
    if (!VALIDATION.EMAIL_PATTERN.test(email)) {
      showError('Введите корректный email.');
      return;
    }

    try {
      setIsSubmittingRequest(true);
      await pricingService.createTurnkeyRequest({
        phone_number: phoneNumber,
        email,
        requested_agent: employeeRequest,
        purpose: employeeRequest,
      });
      setIsRequestModalOpen(false);
      resetRequestForm();
      showSuccess('Заявка успешно создана, мы скоро свяжемся с вами.');
    } catch (error) {
      showError(error?.response?.data?.detail || error?.message || 'Не удалось отправить заявку.');
    } finally {
      setIsSubmittingRequest(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [templatesData, plansData] = await Promise.all([
          pricingService.getAgentTemplates(),
          pricingService.getPlans(),
        ]);
        if (!cancelled) {
          setAgentTemplates(Array.isArray(templatesData?.templates) ? templatesData.templates : []);
          setPolicyNotes(
            Array.isArray(templatesData?.policy_notes) && templatesData.policy_notes.length
              ? templatesData.policy_notes
              : POLICY_NOTES
          );
          setPlans(Array.isArray(plansData?.plans) ? plansData.plans : []);
        }
      } catch (e) {
        if (!cancelled) {
          setAgentTemplates([]);
          setPlans([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;

    const pendingPaymentId = localStorage.getItem(PENDING_YOOKASSA_PAYMENT_ID_KEY);
    if (!pendingPaymentId) return;

    let cancelled = false;
    (async () => {
      try {
        const statusData = await pricingService.getYooKassaPaymentStatus(pendingPaymentId);
        if (cancelled) return;

        if (statusData?.status === 'succeeded') {
          reachYandexGoal(YM_GOALS.TARIFF_PURCHASE_SUCCESS);
          showSuccess('Оплата прошла успешно. Подписка активирована.');
          localStorage.removeItem(PENDING_YOOKASSA_PAYMENT_ID_KEY);
          return;
        }

        if (statusData?.status === 'pending' || statusData?.status === 'waiting_for_capture') {
          showInfo('Платеж еще обрабатывается. Проверьте статус чуть позже.');
          return;
        }

        showError('Оплата не завершена или была отменена.');
        localStorage.removeItem(PENDING_YOOKASSA_PAYMENT_ID_KEY);
      } catch (error) {
        if (!cancelled) {
          showError(error?.message || 'Не удалось проверить статус платежа.');
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, showError, showInfo, showSuccess]);

  const uiPlans = useMemo(() => {
    const featuresByCode = {
      qa: [
        'Ответы по базе знаний (RAG)',
        'Поддержка и консультации 24/7',
        'Токены LLM включены',
      ],
      crm_admin: [
        'Запись, расписание, напоминания',
        'Интеграция с CRM / ERP',
        '1-й месяц обслуживания бесплатно',
      ],
      sales_manager: [
        'Telegram userbot и сценарии продаж',
        'Квалификация и ведение диалога',
        '1-й месяц обслуживания бесплатно',
      ],
    };

    const byCode = Object.fromEntries((agentTemplates || []).map((t) => [t.code, t]));
    const templateCards = ['qa', 'crm_admin', 'sales_manager']
      .map((code) => byCode[code])
      .filter(Boolean)
      .map((template) => {
        const setupRub = Number(template.setup_rub_min || 0);
        const maintenanceRub = Number(template.monthly_maintenance_rub_min || 0);

        return {
          id: template.code,
          name: template.card_title || template.title,
          setupRub,
          maintenanceRub,
          isFree: Boolean(template.is_free),
          requestOnly: false,
          features: featuresByCode[template.code] || [],
        };
      });

    return [
      ...templateCards,
      {
        id: 'turnkey',
        name: 'Под ключ',
        setupRub: 0,
        maintenanceRub: 0,
        isFree: false,
        requestOnly: true,
        features: [
          'Разработка под ваши задачи',
          'Сложные интеграции CRM/ERP',
          'Сопровождение запуска',
        ],
      },
    ];
  }, [agentTemplates]);

  return (
    <MainLayout>
      <div className="pricing-page">
        <div className="pricing-header">
          <h1>Цены на шаблоны агентов</h1>
          <p>Выберите шаблон и запустите агента — оплата минимального запуска при активации</p>
        </div>

        <div className="pricing-grid">
          {uiPlans.map((plan) => (
            <div key={plan.id} className="price-card">
              <h2 className="price-title">{plan.name}</h2>

              <div className="price-old-row price-old-row--placeholder" aria-hidden="true">
                <span className="price-old-value">0 ₽</span>
                <span className="price-discount-badge">-0%</span>
              </div>

              <div className="price-value">
                {plan.requestOnly ? (
                  <span>По запросу</span>
                ) : plan.isFree ? (
                  <span>Бесплатно</span>
                ) : (
                  <>
                    <span className="price-from">от </span>
                    {formatRubPrice(plan.setupRub)}
                    <span className="currency">₽</span>
                  </>
                )}
              </div>

              {plan.requestOnly ? (
                <p className="price-per">Индивидуальный расчёт</p>
              ) : plan.isFree ? (
                <p className="price-per">пробный запуск</p>
              ) : plan.maintenanceRub > 0 ? (
                <p className="price-per">
                  обслуживание от {formatRubPrice(plan.maintenanceRub)} ₽/мес
                </p>
              ) : (
                <p className="price-per price-per--placeholder" aria-hidden="true">
                  &nbsp;
                </p>
              )}

              <ul className="price-features">
                {plan.features.map((feature) => (
                  <li key={feature}>
                    <span className="feature-icon">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className="btn btn-black"
                onClick={() => handleSelectPlan(plan)}
                disabled={isSubmittingRequest}
              >
                {plan.requestOnly
                  ? 'Оставить заявку'
                  : plan.isFree
                    ? 'Попробовать бесплатно'
                    : 'Создать агента'}
              </button>
            </div>
          ))}
        </div>

        <section className="pricing-section" aria-labelledby="pricing-coming-soon-heading">
          <h2 id="pricing-coming-soon-heading" className="pricing-section__title">
            Скоро
          </h2>
          <p className="pricing-section__lead">
            Шаблоны в разработке — скоро появятся на платформе.
          </p>
          <div className="pricing-grid pricing-grid--coming-soon">
            {COMING_SOON_TEMPLATES.map((template) => (
              <div key={template.id} className="price-card price-card--coming-soon">
                <span className="price-soon-badge">Скоро</span>
                <h2 className="price-title">{template.name}</h2>
                <div className="price-value">
                  <span className="price-soon-label">В разработке</span>
                </div>
                <p className="price-per">скоро на платформе</p>
                <ul className="price-features">
                  {template.features.map((feature) => (
                    <li key={feature}>
                      <span className="feature-icon">✓</span>
                      {feature}
                    </li>
                  ))}
                </ul>
                <button type="button" className="btn btn-outline" disabled>
                  Скоро
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="pricing-section" aria-labelledby="pricing-special-heading">
          <h2 id="pricing-special-heading" className="pricing-section__title">
            Спец условия
          </h2>
          <p className="pricing-section__lead">
            Индивидуальные условия для партнёров и независимых специалистов.
          </p>
          <div className="pricing-grid pricing-grid--special">
            {SPECIAL_CONDITIONS.map((offer) => (
              <div key={offer.id} className="price-card price-card--special">
                <h2 className="price-title">{offer.name}</h2>
                <p className="price-special-description">{offer.description}</p>
                <div className="price-value">
                  <span>По запросу</span>
                </div>
                <p className="price-per">индивидуальный расчёт</p>
                <ul className="price-features">
                  {offer.features.map((feature) => (
                    <li key={feature}>
                      <span className="feature-icon">✓</span>
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="btn btn-black"
                  onClick={() => handleOpenSpecialRequest(offer)}
                  disabled={isSubmittingRequest}
                >
                  Оставить заявку
                </button>
              </div>
            ))}
          </div>
        </section>

        <details className="pricing-footnote">
          <summary>Условия тарификации</summary>
          <ul>
            {(policyNotes.length ? policyNotes : POLICY_NOTES).map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      </div>

      {isPurchaseModalOpen && selectedPaidPlan && (
        <div className="pricing-modal-overlay" onClick={handleClosePurchaseModal}>
          <div className="pricing-modal" onClick={(event) => event.stopPropagation()}>
            <h3>Оформление тарифа «{PLAN_DISPLAY_NAMES[selectedPaidPlan.code] || selectedPaidPlan.code}»</h3>
            <div className="pricing-duration-list">
              {DURATION_OPTIONS.map((option) => {
                const optionTotal = calculateTotalForDuration(selectedPaidPlan.price_rub_month, option.months);
                const optionMonthly = Math.round(optionTotal / option.months);
                return (
                  <button
                    type="button"
                    key={option.months}
                    className={`pricing-duration-option ${selectedDurationMonths === option.months ? 'pricing-duration-option--active' : ''}`}
                    onClick={() => setSelectedDurationMonths(option.months)}
                    disabled={isProcessingPayment}
                  >
                    <span
                      className={`pricing-duration-checkpoint ${selectedDurationMonths === option.months ? 'pricing-duration-checkpoint--active' : ''}`}
                      aria-hidden="true"
                    />
                    <span className="pricing-duration-label">{option.label}</span>
                    <span className="pricing-duration-monthly">{formatRubPrice(optionMonthly)} ₽/мес</span>
                    <span className="pricing-duration-total">{formatRubPrice(optionTotal)} ₽</span>
                    <span className={`pricing-duration-discount ${option.discountPercent > 0 ? '' : 'pricing-duration-discount--empty'}`}>
                      {option.discountPercent > 0 ? `-${option.discountPercent}%` : ''}
                    </span>
                  </button>
                );
              })}
            </div>

            <label className="pricing-modal-promo-label" htmlFor="pricing-modal-promo-input">
              Промокод
            </label>
            <input
              id="pricing-modal-promo-input"
              type="text"
              placeholder="Введите код"
              value={purchasePromoCode}
              onChange={(event) => setPurchasePromoCode(event.target.value.toUpperCase())}
              maxLength={64}
              disabled={isProcessingPayment}
              autoComplete="off"
              spellCheck="false"
            />

            <div className="pricing-modal-actions">
              <button type="button" className="btn btn-black" onClick={handleSubmitPurchase} disabled={isProcessingPayment}>
                {isProcessingPayment ? 'Переход к оплате...' : 'Перейти к оплате'}
              </button>
              <button type="button" className="btn btn-outline" onClick={handleClosePurchaseModal} disabled={isProcessingPayment}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
      {isRequestModalOpen && (
        <div className="pricing-modal-overlay" onClick={handleCloseRequestModal}>
          <div className="pricing-modal" onClick={(event) => event.stopPropagation()}>
            <h3>{requestModalConfig.title}</h3>
            <form className="pricing-request-form" onSubmit={handleSubmitTurnkeyRequest}>
              <label>
                Номер телефона
                <input
                  type="tel"
                  value={requestForm.phoneNumber}
                  onChange={(event) => setRequestForm((prev) => ({ ...prev, phoneNumber: event.target.value }))}
                  placeholder="+7 (900) 000-00-00"
                  required
                />
              </label>

              <label>
                Электронная почта
                <input
                  type="email"
                  value={requestForm.email}
                  onChange={(event) => setRequestForm((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="name@company.ru"
                  required
                />
              </label>

              <label>
                Какого сотрудника вы хотите получить
                <textarea
                  value={requestForm.employeeRequest}
                  onChange={(event) => setRequestForm((prev) => ({ ...prev, employeeRequest: event.target.value }))}
                  placeholder={requestModalConfig.requestPlaceholder}
                  rows={4}
                  required
                />
              </label>

              <div className="pricing-modal-actions">
                <button type="submit" className="btn btn-black" disabled={isSubmittingRequest}>
                  {isSubmittingRequest ? 'Отправка...' : 'Отправить заявку'}
                </button>
                <button type="button" className="btn btn-outline" onClick={handleCloseRequestModal}>
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </MainLayout>
  );
};

export default PriceList;