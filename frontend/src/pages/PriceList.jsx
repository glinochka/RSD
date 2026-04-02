/**
 * PriceList Page
 * Display pricing plans and features
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import MainLayout from '../components/Layout';
import { NAVIGATION_ROUTES } from '../config/constants';
import pricingService from '../services/pricingService';
import '../styles/priceList.css';

const PENDING_YOOKASSA_PAYMENT_ID_KEY = 'pending_yookassa_payment_id';
const MARKETING_DISCOUNTS_BY_PLAN = {
  Advanced: 40,
  Pro: 60,
};

const roundUpToNextHundred = (value) => Math.ceil(value / 100) * 100;
const formatRubPrice = (value) => Number(value || 0).toLocaleString('ru-RU');

const PriceList = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError, showInfo, showSuccess } = useNotification();
  const [plans, setPlans] = useState([]);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);

  const handleSelectPlan = async (planId) => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
      return;
    }

    const selectedPlan = plans.find((plan) => plan?.code === planId);
    if (!selectedPlan) {
      showError('Не удалось найти выбранный тариф.');
      return;
    }

    if (!selectedPlan.is_paid) {
      navigate(NAVIGATION_ROUTES.CREATE_AGENT);
      return;
    }

    if (isProcessingPayment) return;
    setIsProcessingPayment(true);
    try {
      const returnUrl = `${window.location.origin}${NAVIGATION_ROUTES.PRICING}`;
      const payment = await pricingService.createYooKassaPayment({
        plan_name: planId,
        return_url: returnUrl,
      });

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
    return sorted.map((plan) => {
      const code = plan?.code;
      const title = plan?.title || code;
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
        currency: '₽',
        period: 'мес',
        per: '',
        features: [
          agentsText,
          `Лимит базы знаний: ${kbText}`,
        ],
      };
    });
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
                {formatRubPrice(plan.price)}
                <span className="currency">{plan.currency}</span>
                <span className="period">/{plan.period}</span>
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
                onClick={() => handleSelectPlan(plan.id)}
                disabled={isProcessingPayment}
              >
                {isProcessingPayment && plan.price > 0 ? 'Переход к оплате...' : 'Выбрать план'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </MainLayout>
  );
};

export default PriceList;