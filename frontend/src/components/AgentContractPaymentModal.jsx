/**
 * Modal to pay or extend a paid agent subscription (YooKassa).
 */

import React, { useEffect, useMemo, useState } from 'react';
import FeatureToggle from './FeatureToggle';
import {
  AGENT_CONTRACT_DURATION_OPTIONS,
  calculateContractTotalRub,
  formatRubPrice,
} from '../utils/agentTemplatePricing';
import '../styles/priceList.css';
import '../styles/featureToggle.css';

const AgentContractPaymentModal = ({
  isOpen,
  agent,
  title,
  onClose,
  onSubmit,
  isProcessing = false,
}) => {
  const billing = agent?.billing || {};
  const monthlyPrice = Number(billing.monthly_price_rub || billing.monthly_maintenance_rub_min || 0);
  const templateTitle = billing.template_title || 'Агент';
  const [durationMonths, setDurationMonths] = useState(1);
  const [promoCode, setPromoCode] = useState('');
  const autopayAvailable = Boolean(
    billing.autopay_available && billing.yookassa_autopay_available !== false,
  );
  const [enableAutopay, setEnableAutopay] = useState(autopayAvailable);

  useEffect(() => {
    if (isOpen) {
      setEnableAutopay(autopayAvailable);
    }
  }, [isOpen, autopayAvailable]);

  const trialHint = useMemo(() => {
    if (billing.maintenance_grace_active && billing.maintenance_grace_until) {
      const days = billing.trial_days_left;
      if (typeof days === 'number') {
        return `Пробный период: осталось ${days} дн. (до ${new Date(billing.maintenance_grace_until).toLocaleDateString('ru-RU')})`;
      }
      return `Пробный период до ${new Date(billing.maintenance_grace_until).toLocaleDateString('ru-RU')}`;
    }
    if (billing.maintenance_paid_until) {
      return `Подписка оплачена до ${new Date(billing.maintenance_paid_until).toLocaleDateString('ru-RU')}`;
    }
    return null;
  }, [billing]);

  const selectedTotal = useMemo(
    () => calculateContractTotalRub(monthlyPrice, durationMonths),
    [monthlyPrice, durationMonths],
  );
  const selectedMonthly = durationMonths > 0 ? Math.round(selectedTotal / durationMonths) : 0;

  if (!isOpen || !agent) return null;

  const handleOverlayClick = () => {
    if (!isProcessing) onClose();
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit({
      agentId: agent.id,
      durationMonths,
      promoCode: promoCode.trim() || undefined,
      enableAutopay: autopayAvailable ? enableAutopay : false,
    });
  };

  return (
    <div className="pricing-modal-overlay" onClick={handleOverlayClick} role="presentation">
      <div
        className="pricing-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-labelledby="agent-contract-modal-title"
      >
        <h3 id="agent-contract-modal-title">
          {title || `Подписка — ${templateTitle}`}
        </h3>
        <p className="pricing-modal-lead">
          {formatRubPrice(monthlyPrice)} ₽/мес · агент #{agent.id}
        </p>
        {trialHint ? <p className="pricing-modal-hint">{trialHint}</p> : null}

        <div className="pricing-duration-list">
          {AGENT_CONTRACT_DURATION_OPTIONS.map((option) => {
            const optionTotal = calculateContractTotalRub(monthlyPrice, option.months);
            const optionMonthly = Math.round(optionTotal / option.months);
            return (
              <button
                type="button"
                key={option.months}
                className={`pricing-duration-option ${durationMonths === option.months ? 'pricing-duration-option--active' : ''}`}
                onClick={() => setDurationMonths(option.months)}
                disabled={isProcessing}
              >
                <span
                  className={`pricing-duration-checkpoint ${durationMonths === option.months ? 'pricing-duration-checkpoint--active' : ''}`}
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

        <p className="pricing-modal-summary">
          К оплате: <strong>{formatRubPrice(selectedTotal)} ₽</strong>
          {' '}
          ({formatRubPrice(selectedMonthly)} ₽/мес)
        </p>

        <form onSubmit={handleSubmit}>
          <label className="pricing-modal-promo-label" htmlFor="agent-contract-promo">
            Промокод
          </label>
          <input
            id="agent-contract-promo"
            type="text"
            placeholder="Введите код"
            value={promoCode}
            onChange={(event) => setPromoCode(event.target.value.toUpperCase())}
            maxLength={64}
            disabled={isProcessing}
            autoComplete="off"
            spellCheck="false"
          />

          {autopayAvailable ? (
            <div className="pricing-modal-autopay-wrap">
              <FeatureToggle
                checked={enableAutopay}
                onChange={setEnableAutopay}
                disabled={isProcessing}
                title="Автопродление подписки"
                description="Списание за выбранный срок за 1 день до окончания. Управление картами — в профиле, «Способы оплаты»."
              />
            </div>
          ) : null}

          <div className="pricing-modal-actions">
            <button type="submit" className="btn btn-black" disabled={isProcessing}>
              {isProcessing ? 'Переход к оплате...' : 'Перейти к оплате'}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
              disabled={isProcessing}
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AgentContractPaymentModal;
