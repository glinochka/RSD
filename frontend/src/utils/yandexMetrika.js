/**
 * Yandex.Metrika reachGoal helpers. Counter id must match frontend/index.html.
 * Create JavaScript-event goals in Metrika with the same ids as YM_GOALS.
 */

const YM_COUNTER_ID = 108582663;

export const YM_GOALS = {
  REGISTRATION_SUCCESS: 'registration_success',
  TARIFF_PURCHASE_SUCCESS: 'tariff_purchase_success',
};

export function reachYandexGoal(goalId) {
  if (typeof window === 'undefined' || typeof window.ym !== 'function') {
    return;
  }
  window.ym(YM_COUNTER_ID, 'reachGoal', goalId);
}
