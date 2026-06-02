/**
 * BookingBlock — mini booking form for admin-template agents.
 */
import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useWebsiteAgent } from '../../context/WebsiteAgentContext';
import { fetchBookingSlots, createBooking } from '../../utils/bookingApi';
import { openAgentWidget } from '../../utils/widget';
import '../../styles/booking-block.css';

const BookingBlock = ({ content, styles = {}, blockStyles = {} }) => {
  const { title = 'Запись на услугу', subtitle = 'Выберите услугу, дату и время' } = content || {};
  const { primaryColor = '#2563EB', backgroundColor = '#F9FAFB', textColor = '#1F2937', darkMode = false } =
    styles;

  const { agentId, services, hasBooking } = useWebsiteAgent();

  const [step, setStep] = useState(1);
  const [serviceId, setServiceId] = useState('');
  const [date, setDate] = useState('');
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [clientName, setClientName] = useState('');
  const [clientPhone, setClientPhone] = useState('');
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const containerBg = darkMode ? '#111827' : backgroundColor;
  const cardBg = darkMode ? '#1F2937' : '#FFFFFF';
  const titleColor = darkMode ? '#FFFFFF' : textColor;

  const availableServices = services?.length ? services : [];

  const loadSlots = useCallback(async () => {
    if (!agentId || !serviceId || !date) return;
    setLoadingSlots(true);
    setError(null);
    setSelectedSlot(null);
    try {
      const items = await fetchBookingSlots(agentId, Number(serviceId), date);
      setSlots(items);
      if (!items.length) {
        setError('На выбранную дату нет свободных слотов');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось загрузить слоты');
      setSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  }, [agentId, serviceId, date]);

  useEffect(() => {
    if (step === 3 && serviceId && date) {
      loadSlots();
    }
  }, [step, serviceId, date, loadSlots]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedSlot || !clientName.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await createBooking(agentId, {
        service_id: Number(serviceId),
        starts_at: selectedSlot.starts_at,
        ends_at: selectedSlot.ends_at,
        client_name: clientName.trim(),
        client_phone: clientPhone.trim() || null,
      });
      setSuccess(result.message || 'Запись успешно создана!');
      setStep(4);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Не удалось создать запись');
    } finally {
      setSubmitting(false);
    }
  };

  if (!hasBooking || !agentId) {
    return (
      <section className="wb-booking py-12 md:py-16" style={{ backgroundColor: containerBg }}>
        <div className="wb-booking__inner">
          <p style={{ color: titleColor, textAlign: 'center' }}>
            Онлайн-запись недоступна для этого сайта
          </p>
        </div>
      </section>
    );
  }

  const minDate = new Date().toISOString().slice(0, 10);

  return (
    <section className="wb-booking py-12 md:py-16 lg:py-20" style={{ backgroundColor: containerBg }}>
      <div className="wb-booking__inner max-w-xl mx-auto px-4">
        <div className="text-center mb-8">
          <h2 className="text-2xl md:text-3xl font-bold mb-2" style={{ color: titleColor }}>
            {title}
          </h2>
          {subtitle && (
            <p className="text-base opacity-80" style={{ color: titleColor }}>
              {subtitle}
            </p>
          )}
        </div>

        <div className="wb-booking__card rounded-2xl p-6 md:p-8 shadow-lg" style={{ backgroundColor: cardBg }}>
          {success && step === 4 ? (
            <div className="wb-booking__success text-center">
              <p className="text-lg font-semibold mb-4" style={{ color: primaryColor }}>
                {success}
              </p>
              <button
                type="button"
                className="wb-booking__btn"
                style={{ backgroundColor: primaryColor }}
                onClick={() => openAgentWidget()}
              >
                Задать вопрос в чате
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              {step === 1 && (
                <div className="wb-booking__step">
                  <label className="wb-booking__label">Услуга</label>
                  <select
                    className="wb-booking__input"
                    value={serviceId}
                    onChange={(e) => setServiceId(e.target.value)}
                    required
                  >
                    <option value="">Выберите услугу</option>
                    {availableServices.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name || s.title} — {s.price}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="wb-booking__btn wb-booking__btn--full mt-4"
                    style={{ backgroundColor: primaryColor }}
                    disabled={!serviceId}
                    onClick={() => setStep(2)}
                  >
                    Далее
                  </button>
                </div>
              )}

              {step === 2 && (
                <div className="wb-booking__step">
                  <label className="wb-booking__label">Дата</label>
                  <input
                    type="date"
                    className="wb-booking__input"
                    min={minDate}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    required
                  />
                  <div className="flex gap-2 mt-4">
                    <button type="button" className="wb-booking__btn wb-booking__btn--ghost" onClick={() => setStep(1)}>
                      Назад
                    </button>
                    <button
                      type="button"
                      className="wb-booking__btn flex-1"
                      style={{ backgroundColor: primaryColor }}
                      disabled={!date}
                      onClick={() => setStep(3)}
                    >
                      Выбрать время
                    </button>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="wb-booking__step">
                  <label className="wb-booking__label">Время</label>
                  {loadingSlots ? (
                    <p className="wb-booking__hint">Загрузка слотов...</p>
                  ) : (
                    <div className="wb-booking__slots">
                      {slots.map((slot, idx) => {
                        const key = slot.starts_at || idx;
                        const label = slot.starts_at
                          ? new Date(slot.starts_at).toLocaleTimeString('ru-RU', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : `Слот ${idx + 1}`;
                        const isSelected =
                          selectedSlot?.starts_at === slot.starts_at &&
                          selectedSlot?.ends_at === slot.ends_at;
                        return (
                          <button
                            key={key}
                            type="button"
                            className={`wb-booking__slot ${isSelected ? 'wb-booking__slot--active' : ''}`}
                            style={
                              isSelected
                                ? { backgroundColor: primaryColor, color: '#fff', borderColor: primaryColor }
                                : {}
                            }
                            onClick={() => setSelectedSlot(slot)}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {selectedSlot && (
                    <>
                      <label className="wb-booking__label mt-4">Ваше имя</label>
                      <input
                        type="text"
                        className="wb-booking__input"
                        value={clientName}
                        onChange={(e) => setClientName(e.target.value)}
                        required
                        maxLength={128}
                      />
                      <label className="wb-booking__label mt-3">Телефон (необязательно)</label>
                      <input
                        type="tel"
                        className="wb-booking__input"
                        value={clientPhone}
                        onChange={(e) => setClientPhone(e.target.value)}
                        maxLength={50}
                      />
                    </>
                  )}

                  <div className="flex gap-2 mt-4">
                    <button type="button" className="wb-booking__btn wb-booking__btn--ghost" onClick={() => setStep(2)}>
                      Назад
                    </button>
                    <button
                      type="submit"
                      className="wb-booking__btn flex-1"
                      style={{ backgroundColor: primaryColor }}
                      disabled={!selectedSlot || !clientName.trim() || submitting}
                    >
                      {submitting ? 'Записываем...' : 'Записаться'}
                    </button>
                  </div>
                </div>
              )}

              {error && <p className="wb-booking__error mt-3">{error}</p>}
            </form>
          )}
        </div>
      </div>
    </section>
  );
};

BookingBlock.propTypes = {
  content: PropTypes.object,
  styles: PropTypes.object,
  blockStyles: PropTypes.object,
};

export default BookingBlock;
