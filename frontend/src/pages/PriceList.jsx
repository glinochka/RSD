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
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
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
    if (plan.requestOnly) {
      setIsRequestModalOpen(true);
      return;
    }

    const selectedPlan = plans.find((p) => p?.code === plan.id);
    if (!selectedPlan) {
      showError('Не удалось найти выбранный тариф.');
      return;
    }

    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
      return;
    }

    if (!selectedPlan.is_paid) {
      navigate(NAVIGATION_ROUTES.CREATE_AGENT);
      return;
    }

    setSelectedPaidPlan(selectedPlan);
    setSelectedDurationMonths(1);
    setPurchasePromoCode('');
    setIsPurchaseModalOpen(true);
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
        const data = await pricingService.getPlans();
        if (!cancelled) setPlans(Array.isArray(data?.plans) ? data.plans : []);
      } catch (e) {
        if (!cancelled) setPlans([]);
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
    const order = { Free: 1, Advanced: 2, Pro: 3 };
    const sorted = [...plans].sort((a, b) => (order[a?.code] ?? 999) - (order[b?.code] ?? 999));
    const mapped = sorted.map((plan) => {
      const code = plan?.code;
      const title = PLAN_DISPLAY_NAMES[code] || plan?.title || code;
      const price = Number(plan?.price_rub_month ?? 0);
      const discountPercent = MARKETING_DISCOUNTS_BY_PLAN[code] ?? null;
      const isPaid = Boolean(plan?.is_paid);
      const originalPrice = isPaid && discountPercent
        ? roundUpToNextHundred(price * (1 + discountPercent / 100))
        : null;
      const kbLimit = plan?.knowledge_base_chunk_limit;
      const maxAgents = Number(plan?.max_active_agents ?? 0);
      const kbText = kbLimit == null ? 'Безлимит' : `${kbLimit} чанков`;
      const agentsText = code === 'Free' ? `${maxAgents} активный агент` : `До ${maxAgents} активных агентов`;

      return {
        id: code,
        name: title,
        price,
        originalPrice,
        discountPercent: isPaid ? discountPercent : null,
        isPaid,
        requestOnly: false,
        currency: '₽',
        period: 'мес',
        per: '',
        features: [
          agentsText,
          `Лимит базы знаний: ${kbText}`,
        ],
      };
    });
    return [
      ...mapped,
      {
        id: 'turnkey',
        name: 'Агент под ключ',
        price: 0,
        originalPrice: null,
        discountPercent: null,
        isPaid: false,
        requestOnly: true,
        currency: '₽',
        period: 'мес',
        per: '',
        features: [
          'Разработка и настройка под ваши задачи',
          'Сопровождение запуска под ключ',
        ],
      },
    ];
  }, [plans]);

  return (
    <MainLayout>
      <div className="pricing-page">
        <div className="pricing-header">
          <h1>Наши тарифные планы</h1>
          <p>Выберите подходящий план для вашего бизнеса</p>
        </div>

        <div className="pricing-grid">
          {uiPlans.map((plan) => (
            <div key={plan.id} className="price-card">
              <h2 className="price-title">{plan.name}</h2>
              <div className={`price-old-row ${plan.isPaid && plan.originalPrice ? '' : 'price-old-row--placeholder'}`}>
                {plan.isPaid && plan.originalPrice ? (
                  <>
                  <span className="price-old-value">
                    {formatRubPrice(plan.originalPrice)}
                    <span className="currency">{plan.currency}</span>
                    <span className="period">/{plan.period}</span>
                  </span>
                  <span className="price-discount-badge">-{plan.discountPercent}%</span>
                  </>
                ) : (
                  <>
                    <span className="price-old-value">0 ₽/мес</span>
                    <span className="price-discount-badge">-0%</span>
                  </>
                )}
              </div>
              <div className="price-value">
                {plan.requestOnly ? (
                  <span>По запросу</span>
                ) : (
                  <>
                    {formatRubPrice(plan.price)}
                    <span className="currency">{plan.currency}</span>
                    <span className="period">/{plan.period}</span>
                  </>
                )}
              </div>
              {plan.per ? <p className="price-per">{plan.per}</p> : null}

              <ul className="price-features">
                {plan.features.map((feature, index) => (
                  <li key={index}>
                    <span className="feature-icon">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                className="btn btn-black"
                onClick={() => handleSelectPlan(plan)}
                disabled={isProcessingPayment || isSubmittingRequest}
              >
                {plan.requestOnly
                  ? 'Оставить заявку'
                  : isProcessingPayment && plan.price > 0
                    ? 'Переход к оплате...'
                    : 'Выбрать план'}
              </button>
            </div>
          ))}
        </div>
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
            <h3>Заявка на тариф «Агент под ключ»</h3>
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
                  placeholder="Опишите роли, задачи и сценарии работы сотрудника"
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