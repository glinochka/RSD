/**
 * Partner program: referral link, promo codes, stats and dynamics.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import referralService from '../services/referralService';
import { buildReferralLink } from '../utils/referralStorage';
import '../styles/partnerPage.css';

const formatRubFromKopecks = (kopecks) =>
  (Number(kopecks || 0) / 100).toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

const PAYOUT_STATUS_LABELS = {
  pending: 'Ожидает проверки',
  approved: 'Одобрена — ожидает перевода',
  paid: 'Выплачена',
  rejected: 'Отклонена',
};

const PartnerPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [dashboard, setDashboard] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [promoDraft, setPromoDraft] = useState({ code: '', discountPercent: 10 });
  const [isSavingPromo, setIsSavingPromo] = useState(false);
  const [actionId, setActionId] = useState(null);
  const [balance, setBalance] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [payoutDraft, setPayoutDraft] = useState({ amountRub: '', paymentDetails: '' });
  const [isSubmittingPayout, setIsSubmittingPayout] = useState(false);

  const referralLink = useMemo(() => {
    if (!dashboard?.referral_code) return '';
    return buildReferralLink(dashboard.referral_code);
  }, [dashboard?.referral_code]);

  const loadPayoutData = useCallback(async () => {
    const [balanceData, payoutsData] = await Promise.all([
      referralService.getPayoutBalance(),
      referralService.getPayouts(),
    ]);
    setBalance(balanceData);
    setPayouts(Array.isArray(payoutsData?.items) ? payoutsData.items : []);
  }, []);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await referralService.getPartnerDashboard();
      setDashboard(data);
      await loadPayoutData();
    } catch (error) {
      showError(error?.message || 'Не удалось загрузить кабинет партнёра');
    } finally {
      setIsLoading(false);
    }
  }, [showError, loadPayoutData]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate(NAVIGATION_ROUTES.AUTH, { replace: true });
      return;
    }
    loadDashboard();
  }, [isAuthenticated, navigate, loadDashboard]);

  const handleCopyLink = async () => {
    if (!referralLink) return;
    try {
      await navigator.clipboard.writeText(referralLink);
      showSuccess('Реферальная ссылка скопирована');
    } catch {
      showError('Не удалось скопировать ссылку');
    }
  };

  const handleCreatePromo = async (event) => {
    event.preventDefault();
    const code = promoDraft.code.trim().toUpperCase();
    const discountPercent = Number(promoDraft.discountPercent);
    if (!code || code.length < 3) {
      showError('Промокод: минимум 3 символа');
      return;
    }
    if (Number.isNaN(discountPercent) || discountPercent < 0 || discountPercent > 50) {
      showError('Скидка от 0 до 50%');
      return;
    }
    setIsSavingPromo(true);
    try {
      await referralService.createPartnerPromoCode({ code, discountPercent });
      setPromoDraft({ code: '', discountPercent: 10 });
      showSuccess('Промокод создан');
      await loadDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось создать промокод');
    } finally {
      setIsSavingPromo(false);
    }
  };

  const handleTogglePromo = async (item) => {
    setActionId(`toggle-${item.id}`);
    try {
      await referralService.patchPartnerPromoCode(item.id, { is_active: !item.is_active });
      await loadDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось обновить промокод');
    } finally {
      setActionId(null);
    }
  };

  const handleCreatePayout = async (event) => {
    event.preventDefault();
    const amountRub = Number(payoutDraft.amountRub);
    const paymentDetails = payoutDraft.paymentDetails.trim();
    const minRub = balance?.min_payout_rub ?? 100;

    if (!Number.isFinite(amountRub) || amountRub < minRub) {
      showError(`Минимальная сумма вывода — ${minRub} ₽`);
      return;
    }
    if (paymentDetails.length < 10) {
      showError('Укажите реквизиты для перевода (минимум 10 символов)');
      return;
    }

    setIsSubmittingPayout(true);
    try {
      await referralService.createPayout({ amountRub, paymentDetails });
      setPayoutDraft({ amountRub: '', paymentDetails: '' });
      showSuccess('Заявка на вывод отправлена');
      await loadPayoutData();
    } catch (error) {
      showError(error?.message || 'Не удалось создать заявку');
    } finally {
      setIsSubmittingPayout(false);
    }
  };

  const handleDeletePromo = async (item) => {
    if (!window.confirm(`Удалить промокод «${item.code}»?`)) return;
    setActionId(`delete-${item.id}`);
    try {
      await referralService.deletePartnerPromoCode(item.id);
      showSuccess('Промокод удалён');
      await loadDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось удалить промокод');
    } finally {
      setActionId(null);
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <MainLayout>
      <div className="partner-page">
        <header className="partner-page__header">
          <div>
            <h1>Партнёрская программа</h1>
            <p className="partner-page__lead">
              Вы получаете {dashboard?.base_commission_percent ?? 50}% с покупок привлечённых пользователей.
              Скидка по вашему промокоду вычитается из вашей доли — до {dashboard?.max_promo_discount_percent ?? 50}%.
            </p>
          </div>
        </header>

        {isLoading ? (
          <Loading />
        ) : (
          <>
            <section className="partner-card">
              <h2>Ваша реферальная ссылка</h2>
              <p className="partner-card__hint">
                Параметр <code>ref</code> сохраняется у гостя на 30 дней. При регистрации клиент закрепляется за вами.
              </p>
              <div className="partner-link-row">
                <input type="text" readOnly value={referralLink} className="partner-link-row__input" />
                <button type="button" className="btn btn-primary" onClick={handleCopyLink}>
                  Копировать
                </button>
              </div>
              <p className="partner-card__meta">
                Код: <strong>{dashboard?.referral_code}</strong>
              </p>
            </section>

            <div className="partner-stats-grid">
              <article className="partner-stat">
                <span className="partner-stat__label">Привлечено рефералов</span>
                <strong className="partner-stat__value">{dashboard?.stats?.referrals_total ?? 0}</strong>
              </article>
              <article className="partner-stat">
                <span className="partner-stat__label">Начислено всего</span>
                <strong className="partner-stat__value">
                  {formatRubFromKopecks(dashboard?.stats?.commission_total_kopecks)} ₽
                </strong>
              </article>
              <article className="partner-stat">
                <span className="partner-stat__label">За 30 дней (комиссия)</span>
                <strong className="partner-stat__value">
                  {formatRubFromKopecks(dashboard?.stats?.commission_period_kopecks)} ₽
                </strong>
              </article>
              <article className="partner-stat">
                <span className="partner-stat__label">Оборот рефералов за 30 дней</span>
                <strong className="partner-stat__value">
                  {formatRubFromKopecks(dashboard?.stats?.payments_period_kopecks)} ₽
                </strong>
              </article>
            </div>

            <section className="partner-card">
              <h2>Вывод средств</h2>
              <p className="partner-card__hint">
                Заявки обрабатываются вручную. После одобрения перевод выполняется с расчётного счёта
                организации (банк, СБП или карта — укажите реквизиты в заявке). Минимум{' '}
                {balance?.min_payout_rub ?? 100} ₽.
              </p>
              <div className="partner-payout-balance">
                <div>
                  <span className="partner-stat__label">Доступно к выводу</span>
                  <strong className="partner-payout-balance__value">
                    {formatRubFromKopecks(balance?.available_kopecks)} ₽
                  </strong>
                </div>
                <div>
                  <span className="partner-stat__label">В обработке</span>
                  <strong>{formatRubFromKopecks(balance?.reserved_kopecks)} ₽</strong>
                </div>
                <div>
                  <span className="partner-stat__label">Уже выплачено</span>
                  <strong>{formatRubFromKopecks(balance?.withdrawn_kopecks)} ₽</strong>
                </div>
              </div>
              <form className="partner-payout-form" onSubmit={handleCreatePayout}>
                <label>
                  Сумма (₽)
                  <input
                    type="number"
                    min={balance?.min_payout_rub ?? 100}
                    step={1}
                    value={payoutDraft.amountRub}
                    onChange={(e) =>
                      setPayoutDraft((prev) => ({ ...prev, amountRub: e.target.value }))
                    }
                    placeholder="100"
                  />
                </label>
                <label>
                  Реквизиты для перевода
                  <textarea
                    rows={3}
                    value={payoutDraft.paymentDetails}
                    onChange={(e) =>
                      setPayoutDraft((prev) => ({ ...prev, paymentDetails: e.target.value }))
                    }
                    placeholder="ФИО, банк, номер карты или телефон для СБП, счёт…"
                  />
                </label>
                <button type="submit" className="btn btn-primary" disabled={isSubmittingPayout}>
                  {isSubmittingPayout ? 'Отправка…' : 'Запросить вывод'}
                </button>
              </form>
              <div className="partner-payout-history">
                <h3>История заявок</h3>
                {payouts.map((item) => (
                  <div key={item.id} className="partner-payout-row">
                    <div>
                      <strong>{formatRubFromKopecks(item.amount_kopecks)} ₽</strong>
                      <span className="partner-payout-row__status">
                        {PAYOUT_STATUS_LABELS[item.status] || item.status}
                      </span>
                      {item.admin_note && (
                        <span className="partner-payout-row__note">{item.admin_note}</span>
                      )}
                    </div>
                    <time>
                      {item.created_at
                        ? new Date(item.created_at).toLocaleString('ru-RU')
                        : '—'}
                    </time>
                  </div>
                ))}
                {!payouts.length && (
                  <p className="partner-card__empty">Заявок на вывод пока нет.</p>
                )}
              </div>
            </section>

            <section className="partner-card">
              <h2>Динамика за 30 дней</h2>
              {dashboard?.timeseries?.length ? (
                <div className="partner-timeseries">
                  {dashboard.timeseries.map((point) => {
                    const maxCommission = Math.max(
                      ...dashboard.timeseries.map((p) => p.commission_kopecks),
                      1,
                    );
                    const height = Math.max(
                      8,
                      Math.round((point.commission_kopecks / maxCommission) * 100),
                    );
                    return (
                      <div key={point.date} className="partner-timeseries__bar-wrap">
                        <div
                          className="partner-timeseries__bar"
                          style={{ height: `${height}%` }}
                          title={`${formatRubFromKopecks(point.commission_kopecks)} ₽`}
                        />
                        <span className="partner-timeseries__label">
                          {point.date.slice(5)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="partner-card__empty">Пока нет начислений за выбранный период.</p>
              )}
            </section>

            <section className="partner-card">
              <h2>Промокоды</h2>
              <p className="partner-card__hint partner-card__hint--winwin">
                Код уникален на всей платформе. Первая оплата с промокодом закрепляет клиента за вами, если он ещё ни за кем не числится.
                Скидка вычитается из ваших 50%: при 10% скидке комиссия 40% от суммы заказа.
              </p>
              <form className="partner-promo-form" onSubmit={handleCreatePromo}>
                <label>
                  Код
                  <input
                    type="text"
                    value={promoDraft.code}
                    onChange={(e) =>
                      setPromoDraft((prev) => ({
                        ...prev,
                        code: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''),
                      }))
                    }
                    placeholder="SALE10"
                    maxLength={32}
                  />
                </label>
                <label>
                  Скидка клиенту (%)
                  <input
                    type="number"
                    min={0}
                    max={50}
                    value={promoDraft.discountPercent}
                    onChange={(e) =>
                      setPromoDraft((prev) => ({ ...prev, discountPercent: e.target.value }))
                    }
                  />
                </label>
                <button type="submit" className="btn btn-primary" disabled={isSavingPromo}>
                  {isSavingPromo ? 'Создание…' : 'Создать'}
                </button>
              </form>

              <div className="partner-promo-table-wrap">
                <table className="partner-promo-table">
                  <thead>
                    <tr>
                      <th>Код</th>
                      <th>Скидка</th>
                      <th>Ваша доля</th>
                      <th>Статус</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {(dashboard?.promo_codes || []).map((item) => (
                      <tr key={item.id}>
                        <td>{item.code}</td>
                        <td>{item.discount_percent}%</td>
                        <td>{item.partner_commission_percent}%</td>
                        <td>{item.is_active ? 'Активен' : 'Выключен'}</td>
                        <td className="partner-promo-table__actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={actionId === `toggle-${item.id}`}
                            onClick={() => handleTogglePromo(item)}
                          >
                            {item.is_active ? 'Выкл.' : 'Вкл.'}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={actionId === `delete-${item.id}`}
                            onClick={() => handleDeletePromo(item)}
                          >
                            Удалить
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!dashboard?.promo_codes?.length && (
                      <tr>
                        <td colSpan={5} className="partner-card__empty">
                          Промокодов пока нет
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="partner-card">
              <h2>Последние начисления</h2>
              <div className="partner-commissions-list">
                {(dashboard?.recent_commissions || []).map((row) => (
                  <div key={row.id} className="partner-commission-row">
                    <div>
                      <strong>+{formatRubFromKopecks(row.commission_amount_kopecks)} ₽</strong>
                      <span className="partner-commission-row__meta">
                        {row.commission_percent}% · заказ {formatRubFromKopecks(row.gross_amount_kopecks)} ₽
                        {row.promo_code ? ` · ${row.promo_code}` : ''}
                      </span>
                    </div>
                    <time>
                      {row.created_at
                        ? new Date(row.created_at).toLocaleString('ru-RU')
                        : '—'}
                    </time>
                  </div>
                ))}
                {!dashboard?.recent_commissions?.length && (
                  <p className="partner-card__empty">Начислений пока нет — поделитесь ссылкой или промокодом.</p>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </MainLayout>
  );
};

export default PartnerPage;
