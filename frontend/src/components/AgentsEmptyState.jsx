import React from 'react';

/**
 * Dashed-border empty state for the agents list (no agents / guest view).
 */
export default function AgentsEmptyState({ message, ctaLabel, onCtaClick }) {
  return (
    <div className="empty-state">
      <p>{message}</p>
      <button type="button" className="btn btn-black" onClick={onCtaClick}>
        {ctaLabel}
      </button>
    </div>
  );
}
