import React from 'react';

const UbtCheck = ({ checked = false, onChange, children, disabled = false }) => (
  <button
    type="button"
    className={`ubt-check ${checked ? 'is-on' : ''}`}
    onClick={() => onChange(!checked)}
    disabled={disabled}
    aria-pressed={checked}
  >
    <span className="ubt-check-box" aria-hidden="true" />
    <span className="ubt-check-label">{children}</span>
  </button>
);

export default UbtCheck;
