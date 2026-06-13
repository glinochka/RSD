/**
 * Profile modal: list saved payment methods and delete cards.
 */

import React, { useCallback, useEffect, useState } from 'react';
import pricingService from '../services/pricingService';
import '../styles/paymentMethodsModal.css';

const PaymentMethodsModal = ({ isOpen, onClose }) => {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState('');

  const loadMethods = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await pricingService.getPaymentMethods();
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setError(err?.message || 'Не удалось загрузить способы оплаты');
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    loadMethods();
  }, [isOpen, loadMethods]);

  if (!isOpen) return null;

  const handleDelete = async (item) => {
    if (!window.confirm(`Удалить карту «${item.title}»? Автопродление агентов с этой картой будет отключено.`)) {
      return;
    }
    setDeletingId(item.id);
    setError('');
    try {
      await pricingService.deletePaymentMethod(item.id);
      await loadMethods();
    } catch (err) {
      setError(err?.message || 'Не удалось удалить карту');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="payment-methods-overlay" onClick={onClose} role="presentation">
      <div
        className="payment-methods-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="payment-methods-title"
      >
        <div className="payment-methods-header">
          <h3 id="payment-methods-title">Способы оплаты</h3>
          <button type="button" className="payment-methods-close" onClick={onClose} aria-label="Закрыть">
            ×
          </button>
        </div>

        <p className="payment-methods-lead">
          Сохранённые карты используются для автопродления подписок на агентов.
          Если удалить все карты, автопродление отключается.
        </p>

        {error ? <p className="payment-methods-error">{error}</p> : null}

        {isLoading ? (
          <p className="payment-methods-empty">Загрузка...</p>
        ) : items.length === 0 ? (
          <p className="payment-methods-empty">Сохранённых карт пока нет. Карта появится после оплаты с включённым автопродлением.</p>
        ) : (
          <ul className="payment-methods-list">
            {items.map((item) => (
              <li key={item.id} className="payment-methods-item">
                <div className="payment-methods-item-info">
                  <span className="payment-methods-item-title">{item.title}</span>
                  {item.created_at ? (
                    <span className="payment-methods-item-meta">
                      Добавлена {new Date(item.created_at).toLocaleDateString('ru-RU')}
                    </span>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="btn btn-outline payment-methods-delete"
                  disabled={deletingId === item.id}
                  onClick={() => handleDelete(item)}
                >
                  {deletingId === item.id ? '...' : 'Удалить'}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="payment-methods-actions">
          <button type="button" className="btn btn-black" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
};

export default PaymentMethodsModal;
