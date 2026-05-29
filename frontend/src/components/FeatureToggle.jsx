/**
 * Shared feature toggle (switch) used across agent settings and payment modal.
 */

import React from 'react';
import '../styles/featureToggle.css';

const FeatureToggle = ({
  checked,
  onChange,
  disabled = false,
  title,
  description,
  compact = false,
}) => (
  <div className={`feature-toggle ${compact ? 'feature-toggle--compact' : ''} ${checked ? 'feature-toggle--on' : ''}`}>
    <button
      type="button"
      className="feature-toggle__main"
      onClick={() => onChange(!checked)}
      disabled={disabled}
      aria-pressed={checked}
    >
      <span className="feature-toggle__content">
        <span className="feature-toggle__title">{title}</span>
        {description ? <span className="feature-toggle__description">{description}</span> : null}
      </span>
      <span className="feature-toggle__switch" aria-hidden="true">
        <span className="feature-toggle__thumb" />
      </span>
    </button>
  </div>
);

export default FeatureToggle;
