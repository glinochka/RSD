import React, { useEffect, useState } from 'react';

const toInt = (value) => {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isNaN(parsed) ? 0 : parsed;
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const UbtStepper = ({ value, min = 0, max = 999, onChange }) => {
  const numeric = clamp(toInt(value), min, max);
  const [draft, setDraft] = useState(String(numeric));
  const [focused, setFocused] = useState(false);
  const digits = Math.max(2, String(Math.max(Math.abs(max), 99)).length);

  useEffect(() => {
    if (!focused) {
      setDraft(String(numeric));
    }
  }, [numeric, focused]);

  const commit = (raw) => {
    const next = raw === '' ? min : clamp(toInt(raw), min, max);
    setDraft(String(next));
    if (next !== numeric) {
      onChange(next);
    }
  };

  const bump = (delta) => {
    const base = draft === '' ? numeric : toInt(draft);
    const next = clamp(base + delta, min, max);
    setDraft(String(next));
    if (next !== numeric) {
      onChange(next);
    }
  };

  return (
    <div className="nc-step">
      <button type="button" onClick={() => bump(-1)} aria-label="Уменьшить">−</button>
      <input
        className="nc-step-input"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        value={focused ? draft : String(numeric)}
        style={{ width: `${digits + 0.8}ch` }}
        aria-label="Значение"
        onChange={(event) => {
          const next = event.target.value;
          if (next === '' || /^\d+$/.test(next)) {
            setDraft(next);
          }
        }}
        onFocus={(event) => {
          const target = event.target;
          setFocused(true);
          setDraft(String(numeric));
          requestAnimationFrame(() => target.select());
        }}
        onBlur={() => {
          setFocused(false);
          commit(draft);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            event.currentTarget.blur();
          }
          if (event.key === 'Escape') {
            setDraft(String(numeric));
            event.currentTarget.blur();
          }
          if (event.key === 'ArrowUp') {
            event.preventDefault();
            bump(1);
          }
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            bump(-1);
          }
        }}
      />
      <button type="button" onClick={() => bump(1)} aria-label="Увеличить">+</button>
    </div>
  );
};

export default UbtStepper;
