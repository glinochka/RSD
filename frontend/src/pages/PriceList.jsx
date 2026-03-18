/**
 * PriceList Page
 * Display pricing plans and features
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import MainLayout from '../components/Layout';
import { PRICING_PLANS, NAVIGATION_ROUTES } from '../config/constants';
import '../styles/priceList.css';

const PriceList = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const handleSelectPlan = (planId) => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH);
      return;
    }
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  };

  return (
    <MainLayout>
      <div className="pricing-page">
        <div className="pricing-header">
          <h1>Наши тарифные планы</h1>
          <p>Выберите подходящий план для вашего бизнеса</p>
        </div>

        <div className="pricing-grid">
          {PRICING_PLANS.map((plan) => (
            <div key={plan.id} className="price-card">
              <h2 className="price-title">{plan.name}</h2>
              <div className="price-value">
                {plan.price}
                <span className="currency">{plan.currency}</span>
                <span className="period">/{plan.period}</span>
              </div>
              <p className="price-per">{plan.per}</p>

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