/**
 * PriceList Page
 * Display pricing plans and features
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import MainLayout from '../components/Layout';
import { NAVIGATION_ROUTES } from '../config/constants';
import pricingService from '../services/pricingService';
import '../styles/priceList.css';

const PriceList = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [plans, setPlans] = useState([]);

  const handleSelectPlan = (planId) => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
      return;
    }
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
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

  const uiPlans = useMemo(() => {
    const order = { Free: 1, Advanced: 2, Pro: 3 };
    const sorted = [...plans].sort((a, b) => (order[a?.code] ?? 999) - (order[b?.code] ?? 999));
    return sorted.map((plan) => {
      const code = plan?.code;
      const title = plan?.title || code;
      const price = Number(plan?.price_rub_month ?? 0);
      const kbLimit = plan?.knowledge_base_chunk_limit;
      const maxAgents = Number(plan?.max_active_agents ?? 0);
      const kbText = kbLimit == null ? 'Безлимит' : `${kbLimit} чанков`;
      const agentsText = code === 'Free' ? `${maxAgents} активный агент` : `До ${maxAgents} активных агентов`;

      return {
        id: code,
        name: title,
        price,
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
              <div className="price-value">
                {plan.price}
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
              >
                Выбрать план
              </button>
            </div>
          ))}
        </div>
      </div>
    </MainLayout>
  );
};

export default PriceList;