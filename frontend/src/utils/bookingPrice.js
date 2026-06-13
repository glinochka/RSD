/** Цены бронирования: в API — копейки (price_minor), в UI — рубли. */

export const rubToMinor = (raw) => {
  const normalized = String(raw ?? '').replace(',', '.').trim();
  const value = Number(normalized);
  if (!Number.isFinite(value) || value < 0) return 0;
  return Math.max(0, Math.round(value * 100));
};

/** Значение для поля ввода «Цена (руб)» из price_minor. */
export const minorToRubInput = (minor) => {
  const m = Number(minor);
  if (!Number.isFinite(m) || m <= 0) return '';
  const rub = m / 100;
  return Number.isInteger(rub) ? String(rub) : rub.toFixed(2);
};

/** Подпись цены в списках услуг. */
export const formatServicePriceLabel = (minorOrRub, { fromMinor = true } = {}) => {
  const rub = fromMinor ? Number(minorOrRub || 0) / 100 : Number(minorOrRub || 0);
  if (!Number.isFinite(rub) || rub < 0) return '0 ₽';
  const text = Number.isInteger(rub)
    ? new Intl.NumberFormat('ru-RU').format(rub)
    : new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(rub);
  return `${text} ₽`;
};
