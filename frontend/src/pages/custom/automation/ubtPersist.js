import { useRef } from 'react';

export function useLiveRef(value) {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}

export function mergeSettings(ref, partial) {
  const merged = { ...(ref.current || {}), ...partial };
  ref.current = merged;
  return merged;
}

export function assertCanRun(saved, offMessage = 'Модуль выключен') {
  if (!saved) {
    throw new Error('Не удалось сохранить настройки');
  }
  if (!saved.enabled) {
    throw new Error(offMessage);
  }
  const issues = saved.issues || [];
  if (issues.length) {
    throw new Error(issues.join('; '));
  }
  return saved;
}
